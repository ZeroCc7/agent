'use strict';

let currentFilename = null;
let resultFilename = null;
let _curveEditor = null;
let _splitToning = { shadow_tint: 0, shadow_tint_strength: 0, highlight_tint: 0, highlight_tint_strength: 0 };
let _autoApplyTimer = null;
let _compareDragging = false;

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('file-input');

  fileInput.addEventListener('change', e => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
  });

  initCurveEditor();

  // Auto-apply on slider / checkbox / select changes in manual panel
  const manualPanel = document.getElementById('cp-manual-body');
  manualPanel.addEventListener('input', e => {
    if (e.target.matches('input[type="range"]')) scheduleAutoApply();
  });
  manualPanel.addEventListener('change', e => {
    if (e.target.matches('input[type="checkbox"], select')) scheduleAutoApply();
  });

  // Before/After drag
  const divider = document.getElementById('compare-divider');
  divider.addEventListener('mousedown', e => {
    _compareDragging = true;
    e.preventDefault();
  });
  divider.addEventListener('touchstart', () => { _compareDragging = true; }, { passive: true });

  document.addEventListener('mousemove', e => {
    if (!_compareDragging) return;
    applyComparePos(e.clientX);
  });
  document.addEventListener('touchmove', e => {
    if (!_compareDragging) return;
    applyComparePos(e.touches[0].clientX);
  }, { passive: true });
  document.addEventListener('mouseup',  () => { _compareDragging = false; });
  document.addEventListener('touchend', () => { _compareDragging = false; });
});

function scheduleAutoApply() {
  if (!currentFilename) return;
  clearTimeout(_autoApplyTimer);
  _autoApplyTimer = setTimeout(applyManualEdit, 800);
}

// ── Before/After comparison ───────────────────────────────────────────
function applyComparePos(clientX) {
  const wrap = document.querySelector('.result-wrap');
  if (!wrap) return;
  const rect = wrap.getBoundingClientRect();
  const pct = Math.max(2, Math.min(98, ((clientX - rect.left) / rect.width) * 100));
  document.getElementById('compare-divider').style.left = pct + '%';
  document.getElementById('result-img').style.clipPath = `inset(0 0 0 ${pct}%)`;
}

function initCompare() {
  const origImg = document.getElementById('original-img');
  if (!origImg.src || origImg.src === window.location.href) return;

  const overlay = document.getElementById('original-overlay');
  overlay.src = origImg.src;
  overlay.classList.remove('hidden');

  const divider = document.getElementById('compare-divider');
  divider.style.left = '50%';
  divider.classList.remove('hidden');

  document.getElementById('result-img').style.clipPath = 'inset(0 0 0 50%)';
  document.getElementById('cmp-label-l').classList.remove('hidden');
  document.getElementById('cmp-label-r').classList.remove('hidden');
}

function resetCompare() {
  document.getElementById('original-overlay').classList.add('hidden');
  document.getElementById('compare-divider').classList.add('hidden');
  document.getElementById('cmp-label-l').classList.add('hidden');
  document.getElementById('cmp-label-r').classList.add('hidden');
  document.getElementById('result-img').style.clipPath = '';
}

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

    document.getElementById('original-img').src = `/uploads/${data.filename}?t=${Date.now()}`;

    // Switch from welcome to editor panels
    document.getElementById('upload-welcome').classList.add('hidden');
    document.getElementById('orig-panel').classList.remove('hidden');
    document.getElementById('result-panel').classList.remove('hidden');

    // Reset result area
    document.getElementById('result-img').src = '';
    document.getElementById('result-img').classList.add('hidden');
    document.getElementById('result-placeholder').classList.remove('hidden');
    document.querySelector('.result-wrap').classList.remove('has-result');
    document.getElementById('download-btn').classList.add('hidden');
    resetCompare();
  } catch (err) {
    alert(err.message);
  } finally {
    hideLoading();
  }
}

function reupload() {
  currentFilename = null;
  resultFilename = null;
  clearTimeout(_autoApplyTimer);
  resetCompare();

  // Switch back to welcome state
  document.getElementById('upload-welcome').classList.remove('hidden');
  document.getElementById('orig-panel').classList.add('hidden');
  document.getElementById('result-panel').classList.add('hidden');
  document.getElementById('original-img').src = '';
  document.getElementById('result-img').src = '';
  document.getElementById('result-img').classList.add('hidden');
  document.getElementById('result-placeholder').classList.remove('hidden');
  document.querySelector('.result-wrap').classList.remove('has-result');
  document.getElementById('download-btn').classList.add('hidden');
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

function toggleCollapse(id, header) {
  const body = document.getElementById(id);
  const isHidden = body.classList.contains('hidden');
  body.classList.toggle('hidden', !isHidden);
  header.classList.toggle('open', isHidden);
}

function getCurrentSliderValues() {
  return {
    brightness:    parseInt(document.getElementById('brightness').value),
    contrast:      parseInt(document.getElementById('contrast').value),
    saturation:    parseInt(document.getElementById('saturation').value),
    sharpness:     parseInt(document.getElementById('sharpness').value),
    color_temp:    parseInt(document.getElementById('colortemp').value),
    smooth_level:  parseInt(document.getElementById('smooth-level').value),
    smooth_skin:   document.getElementById('smooth-skin').checked,
    brighten_skin: document.getElementById('brighten-skin').checked,
    highlights:    parseInt(document.getElementById('highlights').value),
    shadows:       parseInt(document.getElementById('shadows').value),
    whites:        parseInt(document.getElementById('whites').value),
    blacks:        parseInt(document.getElementById('blacks').value),
    vibrance:      parseInt(document.getElementById('vibrance').value),
    clarity:       parseInt(document.getElementById('clarity').value),
    vignette:      parseInt(document.getElementById('vignette').value),
    grain:         parseInt(document.getElementById('grain').value),
  };
}

// ── Section accordion ─────────────────────────────────────────────────
function toggleCpSection(bodyId, header) {
  const body = document.getElementById(bodyId);
  const isHidden = body.classList.contains('hidden');
  body.classList.toggle('hidden', !isHidden);
  header.classList.toggle('open', isHidden);
}

function _expandSection(bodyId) {
  const body = document.getElementById(bodyId);
  if (!body || !body.classList.contains('hidden')) return;
  body.classList.remove('hidden');
  const hdr = body.previousElementSibling;
  if (hdr && hdr.classList.contains('cp-hdr')) hdr.classList.add('open');
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

  // Auto-expand advanced section when any extended param is non-zero
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


// ── Helpers ───────────────────────────────────────────────────────────
function showResult(filename) {
  resultFilename = filename;
  const img = document.getElementById('result-img');
  img.src = `/outputs/${filename}?t=${Date.now()}`;
  img.classList.remove('hidden');
  img.onload = () => {
    document.getElementById('result-placeholder').classList.add('hidden');
    document.querySelector('.result-wrap').classList.add('has-result');
    initCompare();
  };
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

  ['highlights','shadows','whites','blacks','vibrance','clarity','vignette','grain'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.value = 0; updateLabel(el); }
  });
  _splitToning = { shadow_tint: 0, shadow_tint_strength: 0, highlight_tint: 0, highlight_tint_strength: 0 };
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
    document.getElementById('ref-upload-area').classList.add('hidden');
    const saveBtn = document.getElementById('ref-save-btn');
    if (saveBtn) { saveBtn.textContent = '保存为预设'; saveBtn.disabled = false; }
    // Pre-fill agent instruction with reference style if field is empty
    const agentInput = document.getElementById('agentInstruction');
    if (agentInput && !agentInput.value.trim()) {
      agentInput.value = data.explanation || data.style_name || '';
    }
    _updateAgentHint();
  } catch (err) {
    alert('参考图分析失败：' + err.message);
  } finally {
    hideLoading();
  }
}

function _updateAgentHint() {
  const el = document.getElementById('agent-hint');
  if (!el) return;
  if (_referenceFilename) {
    el.innerHTML = '多轮自动迭代，每轮 AI 评分，满意即停（最多 5 轮）<br><span class="agent-ref-badge">已加载参考图，将以匹配参考风格为目标</span>';
  } else {
    el.textContent = '多轮自动迭代，每轮 AI 评分，满意即停（最多 5 轮）';
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
  _expandSection('cp-manual-body');
  applyManualEdit();
}

async function generateFromReference() {
  if (!_referenceParams) return;
  if (!currentFilename) { alert('请先上传图片'); return; }
  const instruction = document.getElementById('ref-explanation').textContent;
  if (!instruction) return;

  showLoading('AI 生成效果图中，约需 20-40 秒...');
  try {
    const res = await fetch('/api/edit/ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: currentFilename, instruction }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'AI 处理失败');
    showResult(data.result_filename);
  } catch (err) {
    alert(err.message);
  } finally {
    hideLoading();
  }
}

async function compareStyle() {
  if (!resultFilename) {
    alert('请先点击「应用参数」生成效果图，再使用 AI 比对');
    return;
  }
  if (!_referenceFilename) return;

  showLoading('AI 比对分析中，约需 10-20 秒...');
  try {
    const res = await fetch('/api/compare-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        result_filename: resultFilename,
        reference_filename: _referenceFilename,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '比对失败');

    applyParamsToSliders(data.params);
    _splitToning = {
      shadow_tint:             data.params.shadow_tint             || 0,
      shadow_tint_strength:    data.params.shadow_tint_strength    || 0,
      highlight_tint:          data.params.highlight_tint          || 0,
      highlight_tint_strength: data.params.highlight_tint_strength || 0,
    };
    if (_curveEditor && data.curve_params) _curveEditor.setData(data.curve_params);

    const expEl = document.getElementById('ref-compare-explanation');
    if (expEl) {
      expEl.textContent = data.explanation;
      expEl.classList.remove('hidden');
    }

    _expandSection('cp-manual-body');
    applyManualEdit();
  } catch (err) {
    alert('AI 比对失败：' + err.message);
  } finally {
    hideLoading();
  }
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
  if (saveBtn) { saveBtn.textContent = '✓ 已保存'; saveBtn.disabled = true; }
}

function showLoading(text = '处理中...') {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
  document.getElementById('loading').classList.add('hidden');
}
