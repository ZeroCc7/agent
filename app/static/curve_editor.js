/**
 * CurveEditor — Canvas-based RGBA curve editor.
 *
 * Usage:
 *   const ed = new CurveEditor(canvasElement);
 *   ed.getData()   → { rgb, r, g, b }  (arrays of [x,y] control points)
 *   ed.setData({ rgb, r, g, b })
 *   ed.setChannel('rgb'|'r'|'g'|'b')
 *   ed.reset()     — reset current channel to identity
 *   ed.resetAll()  — reset all channels
 */
class CurveEditor {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx    = canvas.getContext("2d");

    // Control points per channel: [[x,y], ...] in 0-255 space
    this._pts = {
      rgb: [[0,0],[255,255]],
      r:   [[0,0],[255,255]],
      g:   [[0,0],[255,255]],
      b:   [[0,0],[255,255]],
    };

    this._channel   = "rgb";
    this._dragging  = null;   // index of dragged point
    this._onChange  = null;   // optional callback

    // Convert 0-255 coords ↔ canvas pixels
    this._pad = 18;

    this._bindEvents();
    this.draw();
  }

  /* ── public API ──────────────────────────────────────────────────── */

  setChannel(ch) {
    this._channel = ch;
    this.draw();
  }

  getData() {
    return {
      rgb: this._pts.rgb.map(p => [...p]),
      r:   this._pts.r  .map(p => [...p]),
      g:   this._pts.g  .map(p => [...p]),
      b:   this._pts.b  .map(p => [...p]),
    };
  }

  setData(data) {
    for (const ch of ["rgb","r","g","b"]) {
      if (data[ch]) this._pts[ch] = data[ch].map(p => [...p]);
    }
    this.draw();
  }

  reset() {
    this._pts[this._channel] = [[0,0],[255,255]];
    this.draw();
    if (this._onChange) this._onChange();
  }

  resetAll() {
    for (const ch of ["rgb","r","g","b"])
      this._pts[ch] = [[0,0],[255,255]];
    this.draw();
    if (this._onChange) this._onChange();
  }

  onChange(fn) { this._onChange = fn; }

  /* ── coordinate helpers ──────────────────────────────────────────── */

  _toCanvas(x, y) {
    const { width: W, height: H } = this.canvas;
    const pad = this._pad;
    const inner = Math.min(W, H) - pad * 2;
    return [
      pad + (x / 255) * inner,
      pad + (1 - y / 255) * inner,
    ];
  }

  _toValue(cx, cy) {
    const { width: W, height: H } = this.canvas;
    const pad = this._pad;
    const inner = Math.min(W, H) - pad * 2;
    return [
      Math.round(Math.max(0, Math.min(255, ((cx - pad) / inner) * 255))),
      Math.round(Math.max(0, Math.min(255, (1 - (cy - pad) / inner) * 255))),
    ];
  }

  _hitRadius() { return 10; }

  /* ── PCHIP spline (JS port of curve_processor.py) ───────────────── */

  _buildLut(pts) {
    const sorted = [...pts].sort((a, b) => a[0] - b[0]);
    // Deduplicate by x (last wins already handled by sort stability + reduce)
    const deduped = [];
    const seen = new Map();
    for (const [x, y] of sorted) {
      const cx = Math.max(0, Math.min(255, Math.round(x)));
      const cy = Math.max(0, Math.min(255, Math.round(y)));
      seen.set(cx, cy);
    }
    for (const [x, y] of [...seen.entries()].sort((a, b) => a[0] - b[0]))
      deduped.push([x, y]);

    if (deduped.length < 2) {
      const v = deduped.length === 1 ? deduped[0][1] : 0;
      return new Uint8Array(256).fill(v);
    }

    const xs = deduped.map(p => p[0]);
    const ys = deduped.map(p => p[1]);
    const n  = xs.length;

    // Secant slopes
    const d = new Array(n - 1);
    for (let i = 0; i < n - 1; i++)
      d[i] = (ys[i+1] - ys[i]) / (xs[i+1] - xs[i]);

    // Initial tangents
    const m = new Array(n).fill(0);
    m[0]     = d[0];
    m[n - 1] = d[n - 2];
    for (let i = 1; i < n - 1; i++)
      m[i] = d[i-1] * d[i] <= 0 ? 0 : (d[i-1] + d[i]) / 2;

    // Fritsch-Carlson monotonicity fix
    for (let i = 0; i < n - 1; i++) {
      const di = d[i];
      if (Math.abs(di) < 1e-10) { m[i] = m[i+1] = 0; continue; }
      const a = m[i] / di, b = m[i+1] / di;
      const s2 = a*a + b*b;
      if (s2 > 9) {
        const tau = 3 / Math.sqrt(s2);
        m[i]   = tau * a * di;
        m[i+1] = tau * b * di;
      }
    }

    const lut = new Uint8Array(256);
    for (let x = 0; x < 256; x++) {
      if (x <= xs[0]) {
        lut[x] = Math.max(0, Math.min(255, Math.round(ys[0])));
      } else if (x >= xs[n-1]) {
        lut[x] = Math.max(0, Math.min(255, Math.round(ys[n-1])));
      } else {
        // binary search for segment
        let lo = 0, hi = n - 2;
        while (lo < hi) {
          const mid = (lo + hi + 1) >> 1;
          if (xs[mid] <= x) lo = mid; else hi = mid - 1;
        }
        const i = lo;
        const h = xs[i+1] - xs[i];
        const t = (x - xs[i]) / h;
        const t2 = t*t, t3 = t2*t;
        const y = ys[i]   * (2*t3 - 3*t2 + 1)
                + h*m[i]  * (t3 - 2*t2 + t)
                + ys[i+1] * (-2*t3 + 3*t2)
                + h*m[i+1]* (t3 - t2);
        lut[x] = Math.max(0, Math.min(255, Math.round(y)));
      }
    }
    return lut;
  }

  /* ── drawing ─────────────────────────────────────────────────────── */

  draw() {
    const { canvas, ctx } = this;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const pad   = this._pad;
    const inner = Math.min(W, H) - pad * 2;

    // Background
    ctx.fillStyle = "#1f1f23";
    ctx.fillRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = "#28282e";
    ctx.lineWidth   = 1;
    for (let i = 1; i < 4; i++) {
      const x = pad + (i / 4) * inner;
      const y = pad + (i / 4) * inner;
      ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, pad + inner); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(pad + inner, y); ctx.stroke();
    }

    // Identity diagonal
    ctx.strokeStyle = "#3a3a40";
    ctx.lineWidth   = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(...this._toCanvas(0, 0));
    ctx.lineTo(...this._toCanvas(255, 255));
    ctx.stroke();
    ctx.setLineDash([]);

    // Border
    ctx.strokeStyle = "#3a3a40";
    ctx.lineWidth   = 1;
    ctx.strokeRect(pad, pad, inner, inner);

    // Spline curve
    const pts = this._pts[this._channel];
    const lut = this._buildLut(pts);

    const channelColor = {
      rgb: "#f4f4f5",
      r:   "#ef4444",
      g:   "#22c55e",
      b:   "#3b82f6",
    }[this._channel];

    ctx.strokeStyle = channelColor;
    ctx.lineWidth   = 2;
    ctx.beginPath();
    for (let x = 0; x <= 255; x++) {
      const [cx, cy] = this._toCanvas(x, lut[x]);
      if (x === 0) ctx.moveTo(cx, cy); else ctx.lineTo(cx, cy);
    }
    ctx.stroke();

    // Control points
    const sorted = [...pts].sort((a, b) => a[0] - b[0]);
    for (let i = 0; i < sorted.length; i++) {
      const [cx, cy] = this._toCanvas(sorted[i][0], sorted[i][1]);
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = i === this._dragging ? "#ffffff" : channelColor;
      ctx.fill();
      ctx.strokeStyle = "#1f1f23";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  /* ── mouse / touch events ────────────────────────────────────────── */

  _getPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width  / rect.width;
    const scaleY = this.canvas.height / rect.height;
    const src = e.touches ? e.touches[0] : e;
    return [
      (src.clientX - rect.left) * scaleX,
      (src.clientY - rect.top)  * scaleY,
    ];
  }

  _findPoint(cx, cy) {
    const pts    = this._pts[this._channel];
    const sorted = [...pts].sort((a, b) => a[0] - b[0]);
    const r      = this._hitRadius();
    for (let i = 0; i < sorted.length; i++) {
      const [pcx, pcy] = this._toCanvas(sorted[i][0], sorted[i][1]);
      if (Math.hypot(cx - pcx, cy - pcy) <= r) return i;
    }
    return -1;
  }

  _bindEvents() {
    const el = this.canvas;

    const down = (e) => {
      e.preventDefault();
      const [cx, cy] = this._getPos(e);
      const idx = this._findPoint(cx, cy);
      const pts = this._pts[this._channel];
      const sorted = [...pts].sort((a, b) => a[0] - b[0]);

      if (idx >= 0) {
        this._dragging = idx;
        return;
      }

      // Add new point (not on edge columns to avoid pinning endpoints)
      const [vx, vy] = this._toValue(cx, cy);
      if (vx > 0 && vx < 255) {
        pts.push([vx, vy]);
        pts.sort((a, b) => a[0] - b[0]);
        this._dragging = pts.findIndex(p => p[0] === vx && p[1] === vy);
        this.draw();
        if (this._onChange) this._onChange();
      }
    };

    const move = (e) => {
      e.preventDefault();
      if (this._dragging === null) return;
      const [cx, cy] = this._getPos(e);
      const [vx, vy] = this._toValue(cx, cy);
      const pts    = this._pts[this._channel];
      const sorted = [...pts].sort((a, b) => a[0] - b[0]);

      // Endpoints are x-locked to 0 and 255
      const pt = sorted[this._dragging];
      const isFirst = this._dragging === 0;
      const isLast  = this._dragging === sorted.length - 1;

      if (isFirst)      pt[0] = 0;
      else if (isLast)  pt[0] = 255;
      else              pt[0] = Math.max(1, Math.min(254, vx));
      pt[1] = vy;

      this.draw();
      if (this._onChange) this._onChange();
    };

    const up = (e) => {
      this._dragging = null;
    };

    const dbl = (e) => {
      e.preventDefault();
      const [cx, cy] = this._getPos(e);
      const idx = this._findPoint(cx, cy);
      if (idx < 0) return;
      const pts    = this._pts[this._channel];
      const sorted = [...pts].sort((a, b) => a[0] - b[0]);
      // Don't delete the two endpoints
      if (idx === 0 || idx === sorted.length - 1) return;
      const pt = sorted[idx];
      const i = pts.indexOf(pt);
      if (i >= 0) pts.splice(i, 1);
      this._dragging = null;
      this.draw();
      if (this._onChange) this._onChange();
    };

    el.addEventListener("mousedown",  down,  { passive: false });
    el.addEventListener("mousemove",  move,  { passive: false });
    el.addEventListener("mouseup",    up);
    el.addEventListener("mouseleave", up);
    el.addEventListener("dblclick",   dbl,   { passive: false });
    el.addEventListener("touchstart", down,  { passive: false });
    el.addEventListener("touchmove",  move,  { passive: false });
    el.addEventListener("touchend",   up);
  }
}
