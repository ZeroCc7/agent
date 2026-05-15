# Reference Image Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reference image analysis panel and a preset library modal to the photo editor frontend.

**Architecture:** Pure frontend — 3 files modified (index.html, app.js, style.css). All API endpoints already exist. Task 1 adds extended-param sliders and wires them into the existing manual-edit flow. Task 2 adds the reference image panel. Task 3 adds the preset library modal.

**Tech Stack:** Vanilla JS, HTML, CSS. Existing design system: Caveat + Space Mono fonts, `--paper/--ink/--kraft` color variables, box-shadow offset style.

---

## File Map

| File | Change |
|------|--------|
| `app/static/index.html` | Add extended sliders group, reference panel, preset library button, preset modal |
| `app/static/app.js` | Add `_splitToning` state, update 3 existing functions, add ~10 new functions |
| `app/static/style.css` | Add collapsible header, reference panel, and preset modal toolbar styles |

---

## Task 1: Extended Param Sliders

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

Adds 8 new sliders (highlights/shadows/whites/blacks/vibrance/clarity/vignette/grain) in a collapsible "高级调整" group, wires them into `applyManualEdit`, and adds split-toning state (no sliders — stored in JS, applied when reference params are loaded).

- [ ] **Step 1: Add collapsible CSS to `app/static/style.css`**

Append to the end of `style.css`:

```css
/* ── Collapsible groups ───────────────────────────────────────────────── */
.collapsible-header {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}
.collapsible-header h4 { margin-bottom: 0; border-bottom: none; }
.collapsible-header:hover h4 { color: var(--kraft-dark); }
.collapse-arrow {
  font-family: 'Space Mono', monospace;
  font-size: 0.8rem;
  color: var(--pencil-light);
  display: inline-block;
  transition: transform 0.15s;
}
.collapsible-header.open .collapse-arrow { transform: rotate(90deg); }
.collapsible-body { margin-top: 12px; }
```

- [ ] **Step 2: Add extended sliders HTML to `index.html`**

Locate this comment in `index.html`:
```html
            <!-- Color curve editor -->
```

Insert the following block IMMEDIATELY before that comment:

```html
            <!-- Extended adjustments (collapsible) -->
            <div class="control-group">
              <div class="collapsible-header" onclick="toggleCollapse('advanced-sliders', this)">
                <h4>高级调整</h4>
                <span class="collapse-arrow">▸</span>
              </div>
              <div id="advanced-sliders" class="collapsible-body hidden">
                <div class="slider-row">
                  <label>高光</label>
                  <input type="range" id="highlights" min="-100" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="highlights-val">0</span>
                </div>
                <div class="slider-row">
                  <label>阴影</label>
                  <input type="range" id="shadows" min="-100" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="shadows-val">0</span>
                </div>
                <div class="slider-row">
                  <label>白点</label>
                  <input type="range" id="whites" min="-100" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="whites-val">0</span>
                </div>
                <div class="slider-row">
                  <label>黑点</label>
                  <input type="range" id="blacks" min="-100" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="blacks-val">0</span>
                </div>
                <div class="slider-row">
                  <label>自然饱和</label>
                  <input type="range" id="vibrance" min="-60" max="60" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="vibrance-val">0</span>
                </div>
                <div class="slider-row">
                  <label>清晰度</label>
                  <input type="range" id="clarity" min="-60" max="60" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="clarity-val">0</span>
                </div>
                <div class="slider-row">
                  <label>暗角</label>
                  <input type="range" id="vignette" min="-100" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="vignette-val">0</span>
                </div>
                <div class="slider-row">
                  <label>颗粒感</label>
                  <input type="range" id="grain" min="0" max="100" value="0" oninput="updateLabel(this)">
                  <span class="slider-val" id="grain-val">0</span>
                </div>
              </div>
            </div>

```

- [ ] **Step 3: Update `app.js` — state, `toggleCollapse`, `getCurrentSliderValues`**

At the top of `app.js`, after the existing state declarations (`let currentFilename = null;` etc.), add:

```javascript
let _splitToning = { shadow_tint: 0, shadow_tint_strength: 0, highlight_tint: 0, highlight_tint_strength: 0 };
```

After the `resetAllCurves` function (around line 97), add the two new helpers:

```javascript
function toggleCollapse(id, header) {
  const body = document.getElementById(id);
  const isHidden = body.classList.contains('hidden');
  body.classList.toggle('hidden', !isHidden);
  header.classList.toggle('open', isHidden);
}

function getCurrentSliderValues() {
  return {
    brightness:   parseInt(document.getElementById('brightness').value),
    contrast:     parseInt(document.getElementById('contrast').value),
    saturation:   parseInt(document.getElementById('saturation').value),
    sharpness:    parseInt(document.getElementById('sharpness').value),
    color_temp:   parseInt(document.getElementById('colortemp').value),
    smooth_level: parseInt(document.getElementById('smooth-level').value),
    smooth_skin:  document.getElementById('smooth-skin').checked,
    brighten_skin: document.getElementById('brighten-skin').checked,
    highlights:   parseInt(document.getElementById('highlights').value),
    shadows:      parseInt(document.getElementById('shadows').value),
    whites:       parseInt(document.getElementById('whites').value),
    blacks:       parseInt(document.getElementById('blacks').value),
    vibrance:     parseInt(document.getElementById('vibrance').value),
    clarity:      parseInt(document.getElementById('clarity').value),
    vignette:     parseInt(document.getElementById('vignette').value),
    grain:        parseInt(document.getElementById('grain').value),
  };
}
```

- [ ] **Step 4: Replace `applyParamsToSliders` in `app.js`**

Replace the entire existing `applyParamsToSliders` function with:

```javascript
function applyParamsToSliders(p) {
  const sliderMap = {
    brightness:   'brightness',
    contrast:     'contrast',
    saturation:   'saturation',
    sharpness:    'sharpness',
    color_temp:   'colortemp',
    smooth_level: 'smooth-level',
    highlights:   'highlights',
    shadows:      'shadows',
    whites:       'whites',
    blacks:       'blacks',
    vibrance:     'vibrance',
    clarity:      'clarity',
    vignette:     'vignette',
    grain:        'grain',
  };
  Object.entries(sliderMap).forEach(([key, id]) => {
    if (p[key] === undefined) return;
    const el = document.getElementById(id);
    if (!el) return;
    el.value = p[key];
    updateLabel(el);
    el.classList.add('slider-updated');
    setTimeout(() => el.classList.remove('slider-updated'), 600);
  });

  if (p.smooth_skin !== undefined) {
    document.getElementById('smooth-skin').checked = p.smooth_skin;
    toggleSection('smooth-options', document.getElementById('smooth-skin'));
  }
  if (p.brighten_skin !== undefined) {
    document.getElementById('brighten-skin').checked = p.brighten_skin;
  }
  if (p.background_action !== undefined) {
    document.getElementById('bg-action').value = p.background_action;
  }

  // Auto-expand advanced section when extended params are non-zero
  const hasExtended = ['highlights','shadows','whites','blacks','vibrance','clarity','vignette','grain']
    .some(k => p[k] !== undefined && p[k] !== 0);
  if (hasExtended) {
    const body = document.getElementById('advanced-sliders');
    const header = body?.previousElementSibling;
    if (body?.classList.contains('hidden')) {
      body.classList.remove('hidden');
      header?.classList.add('open');
    }
  }
}
```

- [ ] **Step 5: Replace `resetControls` in `app.js`**

Replace the entire existing `resetControls` function with:

```javascript
function resetControls() {
  ['brightness','contrast','saturation','sharpness'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = 0; updateLabel(el); }
  });
  const ct = document.getElementById('colortemp');
  if (ct) { ct.value = 0; updateLabel(ct); }
  const sl = document.getElementById('smooth-level');
  if (sl) { sl.value = 40; updateLabel(sl); }
  document.getElementById('smooth-skin').checked = false;
  document.getElementById('brighten-skin').checked = false;
  document.getElementById('bg-action').value = 'none';
  document.getElementById('smooth-options').classList.add('hidden');
  if (_curveEditor) _curveEditor.resetAll();

  ['highlights','shadows','whites','blacks','vibrance','clarity','vignette','grain'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = 0; updateLabel(el); }
  });
  _splitToning = { shadow_tint: 0, shadow_tint_strength: 0, highlight_tint: 0, highlight_tint_strength: 0 };
}
```

- [ ] **Step 6: Replace `applyManualEdit` in `app.js`**

Replace the entire existing `applyManualEdit` function with:

```javascript
async function applyManualEdit() {
  if (!currentFilename) return;

  const body = {
    filename: currentFilename,
    edit_params: {
      brightness: sliderToEnhancer('brightness'),
      contrast:   sliderToEnhancer('contrast'),
      saturation: sliderToEnhancer('saturation'),
      sharpness:  sliderToEnhancer('sharpness'),
      color_temp: parseInt(document.getElementById('colortemp').value),
    },
    extended_params: {
      highlights: parseInt(document.getElementById('highlights').value),
      shadows:    parseInt(document.getElementById('shadows').value),
      whites:     parseInt(document.getElementById('whites').value),
      blacks:     parseInt(document.getElementById('blacks').value),
      vibrance:   parseInt(document.getElementById('vibrance').value),
      clarity:    parseInt(document.getElementById('clarity').value),
      vignette:   parseInt(document.getElementById('vignette').value),
      grain:      parseInt(document.getElementById('grain').value),
      ..._splitToning,
    },
    portrait_params: {
      smooth_skin:    document.getElementById('smooth-skin').checked,
      smooth_level:   parseFloat(document.getElementById('smooth-level').value) / 100,
      brighten_skin:  document.getElementById('brighten-skin').checked,
      brighten_level: 0.25,
    },
    background_params: {
      action:      document.getElementById('bg-action').value,
      blur_radius: 15,
    },
    curve_params: getCurveParams(),
  };

  showLoading('处理中...');
  try {
    const res = await fetch('/api/edit/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '处理失败');
    showResult(data.result_filename);
  } catch (err) {
    alert(err.message);
  } finally {
    hideLoading();
  }
}
```

- [ ] **Step 7: Browser verify**

Start the server (`python -m app.main`) and open `http://localhost:8001`. Upload any image. In the manual tab, click "高级调整" — the sliders should expand. Set vignette to -60, click "应用效果" — the result image should show darkened corners.

- [ ] **Step 8: Commit**

```
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat: add extended param sliders (highlights/shadows/vibrance/clarity/vignette/grain)"
```

---

## Task 2: Reference Image Panel

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

Adds a collapsible "参考图" panel below "高级调整". Uploads reference image → calls `/api/analyze-reference` → shows style name + explanation → buttons to apply params, generate AI image, or save as preset.

- [ ] **Step 1: Add reference panel CSS to `style.css`**

Append to the end of `style.css`:

```css
/* ── Reference image panel ───────────────────────────────────────────── */
.ref-hint {
  font-family: 'Space Mono', monospace;
  font-size: 0.65rem;
  color: var(--pencil-light);
  line-height: 1.6;
  margin-bottom: 10px;
}

.ref-result {
  margin-top: 12px;
  border: 2px solid var(--pencil-light);
  background: var(--paper);
  padding: 10px;
}

.ref-result-inner {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.ref-thumb {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border: 2px solid var(--pencil-light);
  flex-shrink: 0;
}

.ref-info { flex: 1; min-width: 0; }

.ref-style-name {
  font-family: 'Caveat', cursive;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 4px;
}

.ref-explanation {
  font-family: 'Space Mono', monospace;
  font-size: 0.62rem;
  color: var(--pencil);
  line-height: 1.5;
}

.ref-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.ref-save-dialog {
  border-top: 1px dashed var(--pencil-light);
  padding-top: 10px;
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ref-save-dialog input[type="text"] {
  font-family: 'Space Mono', monospace;
  font-size: 0.7rem;
  background: var(--paper-warm);
  color: var(--ink);
  border: 2px solid var(--pencil);
  padding: 6px 8px;
  outline: none;
  width: 100%;
}
.ref-save-dialog input[type="text"]:focus { border-color: var(--ink); }

.ref-save-btns { display: flex; gap: 6px; }
```

- [ ] **Step 2: Add reference panel HTML to `index.html`**

Locate this comment in `index.html`:
```html
            <!-- Color curve editor -->
```

Insert the following block IMMEDIATELY before that comment (after the "高级调整" group added in Task 1):

```html
            <!-- Reference image panel -->
            <div class="control-group">
              <div class="collapsible-header" onclick="toggleCollapse('ref-body', this)">
                <h4>参考图</h4>
                <span class="collapse-arrow">▸</span>
              </div>
              <div id="ref-body" class="collapsible-body hidden">
                <p class="ref-hint">上传风格参考图，AI 提取参数填入滑块</p>
                <button class="btn-outline small" onclick="document.getElementById('ref-input').click()">
                  上传参考图
                </button>
                <input type="file" id="ref-input" accept="image/jpeg,image/png,image/webp"
                  style="display:none" onchange="handleReferenceUpload(this.files[0])">

                <div id="ref-result" class="ref-result hidden">
                  <div class="ref-result-inner">
                    <img id="ref-thumb" class="ref-thumb" alt="">
                    <div class="ref-info">
                      <div class="ref-style-name" id="ref-style-name"></div>
                      <div class="ref-explanation" id="ref-explanation"></div>
                    </div>
                  </div>
                  <div class="ref-actions">
                    <button class="btn-ghost small" onclick="applyReferenceParams()">应用参数</button>
                    <button class="btn-ghost small" onclick="generateFromReference()">AI 生成</button>
                    <button class="btn-ghost small" id="ref-save-btn" onclick="openSavePresetDialog()">保存预设</button>
                  </div>
                  <div id="ref-save-dialog" class="ref-save-dialog hidden">
                    <input type="text" id="ref-preset-name" placeholder="预设名称...">
                    <input type="text" id="ref-preset-category" placeholder="分类（可选）">
                    <div class="ref-save-btns">
                      <button class="btn-primary small" onclick="confirmSavePreset()">保存</button>
                      <button class="btn-ghost small" onclick="closeSavePresetDialog()">取消</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

```

- [ ] **Step 3: Add reference image JS functions to `app.js`**

Add a new section at the end of `app.js`, before the `showLoading`/`hideLoading` functions:

```javascript
// ── Reference image analysis ──────────────────────────────────────────
let _referenceFilename = null;
let _referenceParams   = null;
let _referenceCurves   = null;

async function handleReferenceUpload(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  showLoading('上传参考图...');
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '上传失败');
    _referenceFilename = data.filename;
    document.getElementById('ref-thumb').src = `/uploads/${data.filename}?t=${Date.now()}`;
    await analyzeReferenceImage();
  } catch (err) {
    alert('上传失败：' + err.message);
  } finally {
    hideLoading();
  }
}

async function analyzeReferenceImage() {
  showLoading('AI 分析参考图风格...');
  try {
    const res = await fetch('/api/analyze-reference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: _referenceFilename }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '分析失败');

    _referenceParams = data.params;
    _referenceCurves = data.curve_params;

    document.getElementById('ref-style-name').textContent = data.style_name;
    document.getElementById('ref-explanation').textContent = data.explanation;
    document.getElementById('ref-preset-name').value = data.style_name;
    document.getElementById('ref-result').classList.remove('hidden');
    document.getElementById('ref-save-dialog').classList.add('hidden');
    const saveBtn = document.getElementById('ref-save-btn');
    if (saveBtn) { saveBtn.textContent = '保存预设'; saveBtn.disabled = false; }
  } catch (err) {
    alert('参考图分析失败：' + err.message);
  } finally {
    hideLoading();
  }
}

function applyReferenceParams() {
  if (!_referenceParams) return;
  applyParamsToSliders(_referenceParams);
  _splitToning = {
    shadow_tint:             _referenceParams.shadow_tint             || 0,
    shadow_tint_strength:    _referenceParams.shadow_tint_strength    || 0,
    highlight_tint:          _referenceParams.highlight_tint          || 0,
    highlight_tint_strength: _referenceParams.highlight_tint_strength || 0,
  };
  if (_curveEditor && _referenceCurves) _curveEditor.setData(_referenceCurves);
}

function generateFromReference() {
  if (!_referenceParams) return;
  const explanation = document.getElementById('ref-explanation').textContent;
  document.getElementById('ai-instruction').value = explanation;
  // Switch to AI tab
  const aiTabBtn = document.querySelector('.tab[data-tab="ai"]');
  if (aiTabBtn) switchTab(aiTabBtn, 'ai');
}

function openSavePresetDialog() {
  document.getElementById('ref-save-dialog').classList.remove('hidden');
  document.getElementById('ref-preset-name').focus();
}

function closeSavePresetDialog() {
  document.getElementById('ref-save-dialog').classList.add('hidden');
}

async function confirmSavePreset() {
  if (!_referenceParams || !_referenceCurves) return;
  const name = document.getElementById('ref-preset-name').value.trim();
  const category = document.getElementById('ref-preset-category').value.trim();
  if (!name) { alert('请输入预设名称'); return; }

  const res = await fetch('/api/presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      category,
      tags: [],
      params: _referenceParams,
      curve_params: _referenceCurves,
    }),
  });
  if (!res.ok) { const d = await res.json(); alert(d.detail || '保存失败'); return; }

  closeSavePresetDialog();
  const saveBtn = document.getElementById('ref-save-btn');
  if (saveBtn) {
    saveBtn.textContent = '✓ 已保存';
    saveBtn.disabled = true;
  }
}
```

- [ ] **Step 4: Browser verify**

Start the server and open the editor. Upload a main photo. In the manual tab, click "参考图" to expand it. Upload a reference photo (e.g., a photo with warm tones). The analysis loading spinner should appear, then: style name + explanation displayed, thumbnail shown. Click "应用参数" — the sliders should shift and "高级调整" should auto-expand. Click "应用效果" — the result should reflect the reference style.

- [ ] **Step 5: Commit**

```
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat: add reference image analysis panel with apply/generate/save-preset actions"
```

---

## Task 3: Preset Library Modal

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

Adds a "预设库" header button and a modal that lists all saved presets, with "覆盖应用" (replace all params) and "叠加应用" (blend numeric values, OR booleans, replace curves) buttons per preset, plus delete.

- [ ] **Step 1: Add preset modal CSS to `style.css`**

Append to the end of `style.css`:

```css
/* ── Preset Library Modal ────────────────────────────────────────────── */
.modal-toolbar #preset-search {
  flex: 1;
  font-family: 'Space Mono', monospace;
  font-size: 0.72rem;
  background: var(--paper);
  color: var(--ink);
  border: 2px solid var(--pencil);
  border-right: none;
  padding: 7px 10px;
  outline: none;
}
.modal-toolbar #preset-search:focus { border-color: var(--ink); }
.modal-toolbar #preset-category {
  font-family: 'Space Mono', monospace;
  font-size: 0.7rem;
  background: var(--paper);
  color: var(--ink);
  border: 2px solid var(--pencil);
  padding: 7px 10px;
  cursor: pointer;
  outline: none;
  min-width: 120px;
  appearance: none;
  -webkit-appearance: none;
}
.modal-toolbar #preset-category:hover { border-color: var(--ink); }

.preset-list {
  overflow-y: auto;
  padding: 10px;
  background: var(--paper);
  flex: 1;
  min-height: 0;
}
.preset-list::-webkit-scrollbar { width: 5px; }
.preset-list::-webkit-scrollbar-thumb { background: var(--pencil-light); }

.preset-card {
  padding: 10px 12px;
  border: 2px solid var(--pencil-light);
  margin-bottom: 8px;
  background: var(--paper-warm);
}

.pc-tags { margin: 4px 0 8px; display: flex; gap: 4px; flex-wrap: wrap; }
.pc-tag {
  font-family: 'Space Mono', monospace;
  font-size: 0.58rem;
  color: var(--pencil);
  background: var(--paper-grid);
  border: 1px solid var(--pencil-light);
  padding: 1px 6px;
}

.preset-apply-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 6px;
}

/* Preset modal uses full-width single-panel layout */
#preset-modal .modal { max-width: 560px; }
#preset-modal .modal-body-single {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
```

- [ ] **Step 2: Add preset library button to `index.html` header**

Locate this in `index.html`:
```html
      <button class="btn-lib" onclick="openPromptLibrary()">
```

Add the preset library button BEFORE it:

```html
      <button class="btn-lib" onclick="openPresetLibrary()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
        预设库
      </button>
      <button class="btn-lib" onclick="openPromptLibrary()">
```

Wait — the current HTML has just one btn-lib button. The full replacement for that section is:

Locate:
```html
      <button class="btn-lib" onclick="openPromptLibrary()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
        提示词库
      </button>
```

Replace with:
```html
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn-lib" onclick="openPresetLibrary()">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          预设库
        </button>
        <button class="btn-lib" onclick="openPromptLibrary()">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
          提示词库
        </button>
      </div>
```

- [ ] **Step 3: Add preset library modal HTML to `index.html`**

Locate the end of the file, just before `</body>`, and add the preset modal after the existing prompt modal (after `</div>` that closes `#prompt-modal`):

```html
  <!-- Preset Library Modal -->
  <div id="preset-modal" class="modal-overlay hidden" onclick="presetModalOverlayClick(event)">
    <div class="modal">
      <div class="modal-header">
        <h3>预设库</h3>
        <button class="modal-close" onclick="closePresetLibrary()">✕</button>
      </div>
      <div class="modal-toolbar">
        <input type="text" id="preset-search" placeholder="搜索预设名称或标签..."
          oninput="filterPresets()" autocomplete="off">
        <select id="preset-category" onchange="filterPresets()">
          <option value="">全部分类</option>
        </select>
      </div>
      <div class="modal-body-single">
        <div class="preset-list" id="preset-list">
          <div class="list-empty">加载中...</div>
        </div>
      </div>
    </div>
  </div>
```

- [ ] **Step 4: Add preset library JS functions to `app.js`**

Add a new section at the very end of `app.js`:

```javascript
// ── Preset Library ────────────────────────────────────────────────────
let _libPresets = [];

async function openPresetLibrary() {
  document.getElementById('preset-modal').classList.remove('hidden');
  await loadPresets();
}

function closePresetLibrary() {
  document.getElementById('preset-modal').classList.add('hidden');
}

function presetModalOverlayClick(e) {
  if (e.target === document.getElementById('preset-modal')) closePresetLibrary();
}

async function loadPresets() {
  const search = document.getElementById('preset-search').value;
  const category = document.getElementById('preset-category').value;
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (category) params.set('category', category);

  const res = await fetch('/api/presets?' + params);
  const data = await res.json();
  _libPresets = data.presets || [];

  const sel = document.getElementById('preset-category');
  const currentCat = sel.value;
  sel.innerHTML = '<option value="">全部分类</option>';
  (data.categories || []).forEach(c => {
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c;
    if (c === currentCat) opt.selected = true;
    sel.appendChild(opt);
  });

  renderPresetList(_libPresets);
}

function filterPresets() { loadPresets(); }

function renderPresetList(presets) {
  const el = document.getElementById('preset-list');
  if (!presets.length) {
    el.innerHTML = '<div class="list-empty">暂无预设。上传参考图分析后可保存预设。</div>';
    return;
  }
  el.innerHTML = '';
  presets.forEach(p => {
    const div = document.createElement('div');
    div.className = 'preset-card';
    const tagsHtml = (p.tags || []).length
      ? `<div class="pc-tags">${p.tags.map(t => `<span class="pc-tag">${t}</span>`).join('')}</div>`
      : '';
    div.innerHTML =
      `<div class="pc-header">
        <span class="pc-name">${p.name}</span>
        ${p.category ? `<span class="pc-cat">${p.category}</span>` : ''}
      </div>
      ${tagsHtml}
      <div class="preset-apply-row">
        <button class="btn-primary small" onclick="applyPresetById('${p.id}','replace')">覆盖应用</button>
        <button class="btn-ghost small" onclick="applyPresetById('${p.id}','blend')">叠加应用</button>
        <button class="btn-danger small" onclick="deletePresetById('${p.id}')">删除</button>
      </div>`;
    el.appendChild(div);
  });
}

function applyPresetById(id, mode) {
  const p = _libPresets.find(p => p.id === id);
  if (!p) return;
  const params = p.params;
  const curves = p.curve_params;

  if (mode === 'replace') {
    applyParamsToSliders(params);
    _splitToning = {
      shadow_tint:             params.shadow_tint             || 0,
      shadow_tint_strength:    params.shadow_tint_strength    || 0,
      highlight_tint:          params.highlight_tint          || 0,
      highlight_tint_strength: params.highlight_tint_strength || 0,
    };
    if (_curveEditor) _curveEditor.setData(curves);
  } else {
    const avg = (a, b) => Math.round((a + b) / 2);
    const cur = getCurrentSliderValues();
    const blended = {};
    ['brightness','contrast','saturation','sharpness','color_temp',
     'highlights','shadows','whites','blacks','vibrance','clarity','vignette','grain','smooth_level']
      .forEach(k => {
        if (params[k] !== undefined) blended[k] = avg(cur[k] ?? 0, params[k]);
      });
    blended.smooth_skin   = (cur.smooth_skin   || false) || (params.smooth_skin   || false);
    blended.brighten_skin = (cur.brighten_skin  || false) || (params.brighten_skin || false);
    applyParamsToSliders(blended);
    _splitToning = {
      shadow_tint:             params.shadow_tint || 0,
      shadow_tint_strength:    avg(_splitToning.shadow_tint_strength,    params.shadow_tint_strength    || 0),
      highlight_tint:          params.highlight_tint || 0,
      highlight_tint_strength: avg(_splitToning.highlight_tint_strength, params.highlight_tint_strength || 0),
    };
    if (_curveEditor) _curveEditor.setData(curves);
  }

  closePresetLibrary();
}

async function deletePresetById(id) {
  if (!confirm('确认删除这个预设？')) return;
  const res = await fetch(`/api/presets/${id}`, { method: 'DELETE' });
  if (!res.ok) { alert('删除失败'); return; }
  await loadPresets();
}
```

- [ ] **Step 5: Browser verify**

1. Open the editor with a photo loaded.
2. In the reference image panel, upload a reference photo. After analysis, click "保存预设" and enter a name. Click "保存".
3. Click "预设库" in the header. The modal should open and show the saved preset.
4. Click "覆盖应用" — sliders should update and modal should close.
5. Change a few sliders manually. Open preset library again, click "叠加应用" on the same preset — slider values should be averaged.
6. Open preset library, click "删除" — confirm dialog appears, preset removed from list.

- [ ] **Step 6: Commit**

```
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat: add preset library modal with replace/blend apply modes"
```

---

## Self-Review

**Spec coverage:**
- ✅ Reference image panel: upload → analyze → apply params → save preset → AI generate
- ✅ Extended param sliders (8 sliders + split toning in JS state)
- ✅ Preset library modal: list, search by name/tag, filter by category, apply (replace/blend), delete
- ✅ Apply mode: replace overwrites all params; blend averages numerics, ORs booleans, replaces curves

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency:**
- `applyParamsToSliders` used in Task 1, Task 2 (`applyReferenceParams`), Task 3 (`applyPresetById`) — same function name throughout ✅
- `_splitToning` initialized in Task 1, read in `applyManualEdit` (Task 1), written in Tasks 2 and 3 ✅
- `getCurrentSliderValues` added in Task 1, used in Task 3 (`applyPresetById` blend mode) ✅
- `toggleCollapse` added in Task 1, used in Task 2 HTML (`ref-body`) ✅
