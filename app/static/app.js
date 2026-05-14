'use strict';

let currentFilename = null;
let resultFilename = null;

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  fileInput.addEventListener('change', e => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
  });
});

// ── Upload ────────────────────────────────────────────────────────────
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  showLoading('上传中...');
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '上传失败');

    currentFilename = data.filename;
    resultFilename = null;

    const originalImg = document.getElementById('original-img');
    const resultImg = document.getElementById('result-img');
    originalImg.src = `/uploads/${data.filename}?t=${Date.now()}`;
    resultImg.src = `/uploads/${data.filename}?t=${Date.now()}`;

    document.getElementById('result-img').onload = () => {
      document.querySelector('.result-wrap').classList.remove('has-result');
    };

    document.getElementById('download-btn').classList.add('hidden');
    document.getElementById('ai-explanation').classList.add('hidden');

    document.getElementById('upload-section').classList.add('hidden');
    document.getElementById('editor-section').classList.remove('hidden');
  } catch (err) {
    alert(err.message);
  } finally {
    hideLoading();
  }
}

function reupload() {
  currentFilename = null;
  resultFilename = null;
  document.getElementById('editor-section').classList.add('hidden');
  document.getElementById('upload-section').classList.remove('hidden');
  document.getElementById('file-input').value = '';
  resetControls();
}

// ── Tabs ──────────────────────────────────────────────────────────────
function switchTab(btn, name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`panel-${name}`).classList.remove('hidden');
}

// ── Slider labels ─────────────────────────────────────────────────────
function updateLabel(slider) {
  const el = document.getElementById(slider.id + '-val');
  if (el) el.textContent = slider.value;
}

function toggleSection(id, checkbox) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('hidden', !checkbox.checked);
}

function setExample(el) {
  document.getElementById('ai-instruction').value = el.textContent;
}

// ── Manual edit ───────────────────────────────────────────────────────
// Sliders go -60..60; backend EditParams expect Pillow enhancer values (1.0 = original)
function sliderToEnhancer(id) {
  return 1.0 + parseFloat(document.getElementById(id).value) / 100.0;
}

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

// ── AI edit ───────────────────────────────────────────────────────────
async function applyAIEdit() {
  if (!currentFilename) return;

  const instruction = document.getElementById('ai-instruction').value.trim();
  if (!instruction) { alert('请描述你想要的效果'); return; }

  showLoading('AI 生图中，约需 20-40 秒...');
  try {
    const res = await fetch('/api/edit/ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: currentFilename, instruction }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'AI 处理失败');

    showResult(data.result_filename);

    const explEl = document.getElementById('ai-explanation');
    if (data.ai_explanation) {
      explEl.textContent = 'AI 说：' + data.ai_explanation;
      explEl.classList.remove('hidden');
    } else {
      explEl.classList.add('hidden');
    }
  } catch (err) {
    alert(err.message);
  } finally {
    hideLoading();
  }
}

// ── Helpers ───────────────────────────────────────────────────────────
function showResult(filename) {
  resultFilename = filename;
  const img = document.getElementById('result-img');
  img.src = `/outputs/${filename}?t=${Date.now()}`;
  img.onload = () => document.querySelector('.result-wrap').classList.add('has-result');
  document.getElementById('download-btn').classList.remove('hidden');
}

function downloadResult() {
  if (!resultFilename) return;
  const a = document.createElement('a');
  a.href = `/outputs/${resultFilename}?t=${Date.now()}`;
  a.download = `edited_${resultFilename}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

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
}

function showLoading(text = '处理中...') {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
  document.getElementById('loading').classList.add('hidden');
}
