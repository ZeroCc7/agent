'use strict';

let currentFilename = null;
let resultFilename = null;
let _curveEditor = null;

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
    document.getElementById('suggestion-area').classList.add('hidden');
    document.getElementById('suggestion-grid').innerHTML = '';
    document.getElementById('ai-instruction').value = '';

    document.getElementById('upload-section').classList.add('hidden');
    document.getElementById('editor-section').classList.remove('hidden');
    initCurveEditor();
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

// ── Curve editor ─────────────────────────────────────────────────────
function initCurveEditor() {
  if (_curveEditor) return;
  const canvas = document.getElementById('curve-canvas');
  if (!canvas) return;
  _curveEditor = new CurveEditor(canvas);
}

function switchCurveTab(btn, ch) {
  document.querySelectorAll('.curve-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  if (_curveEditor) _curveEditor.setChannel(ch);
}

function resetCurrentCurve() {
  if (_curveEditor) _curveEditor.reset();
}

function resetAllCurves() {
  if (_curveEditor) _curveEditor.resetAll();
}

function getCurveParams() {
  if (!_curveEditor) return { rgb: [[0,0],[255,255]], r: [[0,0],[255,255]], g: [[0,0],[255,255]], b: [[0,0],[255,255]] };
  return _curveEditor.getData();
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

// ── AI parameter suggestion ───────────────────────────────────────────
async function getSuggestion() {
  const instruction = document.getElementById('assist-input').value.trim();
  if (!instruction) { alert('请输入描述'); return; }

  const btn = document.getElementById('assist-btn');
  btn.textContent = '解读中...';
  btn.disabled = true;

  const current = {
    brightness:        parseInt(document.getElementById('brightness').value),
    contrast:          parseInt(document.getElementById('contrast').value),
    saturation:        parseInt(document.getElementById('saturation').value),
    sharpness:         parseInt(document.getElementById('sharpness').value),
    color_temp:        parseInt(document.getElementById('colortemp').value),
    smooth_skin:       document.getElementById('smooth-skin').checked,
    smooth_level:      parseInt(document.getElementById('smooth-level').value),
    brighten_skin:     document.getElementById('brighten-skin').checked,
    background_action: document.getElementById('bg-action').value,
  };

  try {
    const res = await fetch('/api/edit/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction, current_params: current }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '解读失败');

    applyParamsToSliders(data.params);

    if (data.curve_params && _curveEditor) {
      _curveEditor.setData(data.curve_params);
      // Switch to RGB tab so user sees the change
      const rgbTab = document.querySelector('.curve-tab[data-ch="rgb"]');
      if (rgbTab) switchCurveTab(rgbTab, 'rgb');
    }

    const el = document.getElementById('assist-explanation');
    el.textContent = data.explanation || '';
    el.classList.toggle('hidden', !data.explanation);
  } catch (err) {
    alert('AI 解读失败：' + err.message);
  } finally {
    btn.textContent = '解读';
    btn.disabled = false;
  }
}

function applyParamsToSliders(p) {
  // Slider IDs differ from param keys for color_temp and smooth_level
  const sliderMap = {
    brightness:   'brightness',
    contrast:     'contrast',
    saturation:   'saturation',
    sharpness:    'sharpness',
    color_temp:   'colortemp',
    smooth_level: 'smooth-level',
  };
  Object.entries(sliderMap).forEach(([key, id]) => {
    if (p[key] === undefined) return;
    const el = document.getElementById(id);
    if (!el) return;
    el.value = p[key];
    updateLabel(el);
    // Brief flash to show the slider changed
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
}

// ── Photo analysis ────────────────────────────────────────────────────
async function analyzePhoto() {
  if (!currentFilename) return;

  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  showLoading('AI 分析照片中...');

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: currentFilename }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '分析失败');
    renderSuggestions(data.suggestions);
  } catch (err) {
    alert('照片分析失败：' + err.message);
  } finally {
    btn.disabled = false;
    hideLoading();
  }
}

function renderSuggestions(suggestions) {
  const grid = document.getElementById('suggestion-grid');
  grid.innerHTML = '';

  suggestions.forEach(s => {
    const card = document.createElement('div');
    card.className = 'suggestion-card';
    // Escape for inline onclick attribute
    const escapedPrompt = s.prompt.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const escapedStyle = s.style.replace(/'/g, "\\'");
    const escapedDesc = s.description.replace(/'/g, "\\'");
    card.innerHTML =
      `<div class="card-style">${s.style}</div>` +
      `<div class="card-desc">${s.description}</div>` +
      `<button class="pc-save-btn" onclick="saveToLibrary(event,'${escapedStyle}','${escapedPrompt}','${escapedDesc}')">保存到库</button>`;
    card.addEventListener('click', e => {
      if (!e.target.closest('.pc-save-btn')) selectSuggestion(card, s.prompt);
    });
    grid.appendChild(card);
  });

  document.getElementById('suggestion-area').classList.remove('hidden');
  // Auto-select the first card
  if (grid.firstChild) grid.firstChild.click();
}

function selectSuggestion(card, prompt) {
  document.querySelectorAll('.suggestion-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  document.getElementById('ai-instruction').value = prompt;
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
  if (_curveEditor) _curveEditor.resetAll();
}

// ── Prompt Library ────────────────────────────────────────────────────
let _libPrompts = [];
let _selectedPromptId = null;   // null = new prompt

async function openPromptLibrary() {
  document.getElementById('prompt-modal').classList.remove('hidden');
  await loadLibraryPrompts();
}

function closePromptLibrary() {
  document.getElementById('prompt-modal').classList.add('hidden');
}

function modalOverlayClick(e) {
  if (e.target === document.getElementById('prompt-modal')) closePromptLibrary();
}

async function loadLibraryPrompts() {
  const search = document.getElementById('lib-search').value;
  const category = document.getElementById('lib-category').value;
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (category) params.set('category', category);

  const res = await fetch('/api/prompts?' + params);
  const data = await res.json();
  _libPrompts = data.prompts || [];

  // Rebuild category dropdown, keep current selection
  const sel = document.getElementById('lib-category');
  const currentCat = sel.value;
  sel.innerHTML = '<option value="">全部分类</option>';
  (data.categories || []).forEach(c => {
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c;
    if (c === currentCat) opt.selected = true;
    sel.appendChild(opt);
  });

  renderPromptList(_libPrompts);
}

function filterPrompts() { loadLibraryPrompts(); }

function renderPromptList(prompts) {
  const el = document.getElementById('prompt-list');
  if (!prompts.length) {
    el.innerHTML = '<div class="list-empty">暂无提示词，点击「新增」添加</div>';
    return;
  }
  el.innerHTML = '';
  prompts.forEach(p => {
    const div = document.createElement('div');
    div.className = 'prompt-card' + (p.id === _selectedPromptId ? ' selected' : '');
    div.dataset.id = p.id;
    div.innerHTML =
      `<div class="pc-header">
        <span class="pc-name">${p.name}</span>
        ${p.category ? `<span class="pc-cat">${p.category}</span>` : ''}
      </div>
      <div class="pc-preview">${p.prompt.slice(0, 80)}${p.prompt.length > 80 ? '…' : ''}</div>`;
    div.addEventListener('click', () => selectLibraryPrompt(p.id));
    el.appendChild(div);
  });
}

function selectLibraryPrompt(id) {
  _selectedPromptId = id;
  document.querySelectorAll('.prompt-card').forEach(c =>
    c.classList.toggle('selected', c.dataset.id === id)
  );
  const p = _libPrompts.find(p => p.id === id);
  if (!p) return;
  showPromptForm(p);
}

function startNewPrompt() {
  _selectedPromptId = null;
  document.querySelectorAll('.prompt-card').forEach(c => c.classList.remove('selected'));
  showPromptForm(null);
}

function showPromptForm(p) {
  document.getElementById('edit-empty').classList.add('hidden');
  const form = document.getElementById('prompt-form');
  form.classList.remove('hidden');

  document.getElementById('pf-name').value = p?.name || '';
  document.getElementById('pf-category').value = p?.category || '';
  document.getElementById('pf-tags').value = (p?.tags || []).join(', ');
  document.getElementById('pf-prompt').value = p?.prompt || '';
  document.getElementById('pf-delete').style.display = p ? '' : 'none';
}

async function saveCurrentPrompt() {
  const name = document.getElementById('pf-name').value.trim();
  const prompt = document.getElementById('pf-prompt').value.trim();
  const category = document.getElementById('pf-category').value.trim();
  const tags = document.getElementById('pf-tags').value.split(',').map(t => t.trim()).filter(Boolean);

  if (!name) { alert('请填写名称'); return; }
  if (!prompt) { alert('请填写提示词内容'); return; }

  const isNew = !_selectedPromptId;
  const url = isNew ? '/api/prompts' : `/api/prompts/${_selectedPromptId}`;
  const method = isNew ? 'POST' : 'PUT';

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, prompt, category, tags }),
  });
  if (!res.ok) { const d = await res.json(); alert(d.detail || '保存失败'); return; }
  const saved = await res.json();
  _selectedPromptId = saved.id;
  await loadLibraryPrompts();
  // Re-highlight the saved card
  selectLibraryPrompt(saved.id);
}

async function deleteCurrentPrompt() {
  if (!_selectedPromptId) return;
  if (!confirm('确认删除这条提示词？')) return;
  const res = await fetch(`/api/prompts/${_selectedPromptId}`, { method: 'DELETE' });
  if (!res.ok) { alert('删除失败'); return; }
  _selectedPromptId = null;
  document.getElementById('prompt-form').classList.add('hidden');
  document.getElementById('edit-empty').classList.remove('hidden');
  await loadLibraryPrompts();
}

function useCurrentPrompt() {
  const text = document.getElementById('pf-prompt').value.trim();
  if (!text) return;
  document.getElementById('ai-instruction').value = text;
  closePromptLibrary();
}

// Save an AI-generated suggestion straight to the library
async function saveToLibrary(event, style, promptText, description) {
  event.stopPropagation();
  const btn = event.currentTarget;
  const res = await fetch('/api/prompts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: style, prompt: promptText, category: 'AI生成', tags: [] }),
  });
  if (res.ok) {
    btn.textContent = '✓ 已保存';
    btn.disabled = true;
  } else {
    alert('保存失败');
  }
}

function showLoading(text = '处理中...') {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
  document.getElementById('loading').classList.add('hidden');
}
