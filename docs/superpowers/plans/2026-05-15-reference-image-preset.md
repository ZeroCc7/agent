# Reference Image Style Extraction + Parameter Preset Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reference-image style extraction (Qwen-VL → slider params + curves) and a standalone parameter preset library to the AI photo editor.

**Architecture:** A new `reference_analyzer.py` calls DashScope Qwen-VL (same pattern as `image_analyzer.py`) and returns a full parameter dict. A new `preset_store.py` (mirrors `prompt_store.py`) persists named presets to `data/presets.json`. `image_processor.py` gains `apply_extended_edits` for the new tonal/style parameters. All wired into `routes.py` as new endpoints.

**Tech Stack:** Python 3.9, FastAPI, Pydantic v2, Pillow, NumPy, OpenCV (`cv2`), DashScope SDK, pytest, httpx

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Modify | Add pytest, httpx, pytest-mock |
| `app/types/models.py` | Modify | Add `ExtendedEditParams`, extend `CurrentParams`, add `Preset*`, `ReferenceAnalyze*`, update `ManualEditRequest` |
| `app/core/preset_store.py` | Create | File-based CRUD for parameter presets (`data/presets.json`) |
| `app/core/reference_analyzer.py` | Create | Qwen-VL call + JSON parsing to extract style params from reference image |
| `app/core/image_processor.py` | Modify | Add `apply_extended_edits` + helper functions |
| `app/api/routes.py` | Modify | Add `/api/analyze-reference` and `/api/presets` route group |
| `app/main.py` | Modify | Add `Path("data").mkdir(exist_ok=True)` |
| `tests/__init__.py` | Create | Empty — marks tests as package |
| `tests/conftest.py` | Create | Shared fixtures (tmp data dir, test image) |
| `tests/test_models.py` | Create | Model defaults and validation |
| `tests/test_preset_store.py` | Create | preset_store CRUD |
| `tests/test_reference_analyzer.py` | Create | reference_analyzer parsing + fallback |
| `tests/test_image_processor_extended.py` | Create | apply_extended_edits per-function |
| `tests/test_routes.py` | Create | API endpoint integration tests |

---

## Task 1: Setup Test Infrastructure

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Add these lines to `requirements.txt`:
```
pytest>=8.0.0
httpx>=0.27.0
pytest-mock>=3.14.0
```

- [ ] **Step 2: Install new dependencies**

```
pip install pytest httpx pytest-mock
```

Expected: installs without error.

- [ ] **Step 3: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import io
import os
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_data_dir(tmp_path, monkeypatch):
    """Redirect data/presets.json to a temp dir for every test."""
    import app.core.preset_store as ps
    monkeypatch.setattr(ps, "DATA_FILE", tmp_path / "presets.json")


@pytest.fixture()
def test_image() -> Image.Image:
    """100×100 solid-color RGB image for processor tests."""
    return Image.new("RGB", (100, 100), color=(120, 80, 60))


@pytest.fixture()
def test_image_path(tmp_path, test_image) -> Path:
    """Save test image to disk and return path."""
    p = tmp_path / "ref.jpg"
    test_image.save(p, "JPEG")
    return p


@pytest.fixture()
def client():
    """FastAPI TestClient with uploads/outputs redirected to tmp dirs."""
    from app.main import app
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 5: Verify pytest discovers tests**

```
pytest --collect-only
```

Expected: `no tests ran` (no test files yet) with exit code 5 (no tests collected) — not an error.

- [ ] **Step 6: Commit**

```
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "test: setup pytest infrastructure"
```

---

## Task 2: Extend Data Models

**Files:**
- Modify: `app/types/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
from app.types.models import (
    ExtendedEditParams, CurrentParams, ManualEditRequest,
    Preset, PresetCreate, PresetUpdate,
    ReferenceAnalyzeRequest, ReferenceAnalyzeResponse, CurveParams,
)


def test_extended_edit_params_defaults():
    p = ExtendedEditParams()
    assert p.highlights == 0
    assert p.shadows == 0
    assert p.whites == 0
    assert p.blacks == 0
    assert p.vibrance == 0
    assert p.clarity == 0
    assert p.vignette == 0
    assert p.grain == 0
    assert p.shadow_tint == 0
    assert p.shadow_tint_strength == 0
    assert p.highlight_tint == 0
    assert p.highlight_tint_strength == 0


def test_current_params_has_extended_fields():
    p = CurrentParams()
    assert hasattr(p, "highlights")
    assert hasattr(p, "shadows")
    assert hasattr(p, "vibrance")
    assert hasattr(p, "clarity")
    assert hasattr(p, "vignette")
    assert hasattr(p, "grain")
    assert hasattr(p, "shadow_tint")
    assert hasattr(p, "highlight_tint")


def test_manual_edit_request_has_extended_params():
    r = ManualEditRequest(filename="test.jpg")
    assert hasattr(r, "extended_params")
    assert isinstance(r.extended_params, ExtendedEditParams)


def test_preset_create_roundtrip():
    pc = PresetCreate(
        name="日系清透",
        params=CurrentParams(),
        curve_params=CurveParams(),
        category="人像",
        tags=["日系"],
    )
    assert pc.name == "日系清透"
    assert pc.category == "人像"


def test_reference_analyze_response():
    r = ReferenceAnalyzeResponse(
        params=CurrentParams(),
        curve_params=CurveParams(),
        style_name="胶片复古",
        explanation="暗部提亮，整体偏暖",
    )
    assert r.style_name == "胶片复古"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_models.py -v
```

Expected: `ImportError` — `ExtendedEditParams` not defined yet.

- [ ] **Step 3: Implement model extensions in `app/types/models.py`**

Add `ExtendedEditParams` after the existing `BackgroundParams` class:

```python
class ExtendedEditParams(BaseModel):
    highlights: int = Field(0, ge=-100, le=100)
    shadows: int = Field(0, ge=-100, le=100)
    whites: int = Field(0, ge=-100, le=100)
    blacks: int = Field(0, ge=-100, le=100)
    vibrance: int = Field(0, ge=-60, le=60)
    clarity: int = Field(0, ge=-60, le=60)
    vignette: int = Field(0, ge=-100, le=100)
    grain: int = Field(0, ge=0, le=100)
    shadow_tint: int = Field(0, ge=0, le=360)
    shadow_tint_strength: int = Field(0, ge=0, le=100)
    highlight_tint: int = Field(0, ge=0, le=360)
    highlight_tint_strength: int = Field(0, ge=0, le=100)
```

Update `ManualEditRequest` to include `extended_params`:

```python
class ManualEditRequest(BaseModel):
    filename: str
    edit_params: EditParams = EditParams()
    portrait_params: PortraitParams = PortraitParams()
    background_params: BackgroundParams = BackgroundParams()
    curve_params: CurveParams = Field(default_factory=CurveParams)
    extended_params: ExtendedEditParams = Field(default_factory=ExtendedEditParams)
```

Extend `CurrentParams` with the new fields (add after `background_action`):

```python
class CurrentParams(BaseModel):
    brightness: int = Field(0, ge=-60, le=60)
    contrast: int = Field(0, ge=-60, le=60)
    saturation: int = Field(0, ge=-60, le=60)
    sharpness: int = Field(0, ge=-60, le=60)
    color_temp: int = Field(0, ge=-100, le=100)
    smooth_skin: bool = False
    smooth_level: int = Field(40, ge=0, le=100)
    brighten_skin: bool = False
    background_action: Literal["none", "blur", "remove"] = "none"
    highlights: int = Field(0, ge=-100, le=100)
    shadows: int = Field(0, ge=-100, le=100)
    whites: int = Field(0, ge=-100, le=100)
    blacks: int = Field(0, ge=-100, le=100)
    vibrance: int = Field(0, ge=-60, le=60)
    clarity: int = Field(0, ge=-60, le=60)
    vignette: int = Field(0, ge=-100, le=100)
    grain: int = Field(0, ge=0, le=100)
    shadow_tint: int = Field(0, ge=0, le=360)
    shadow_tint_strength: int = Field(0, ge=0, le=100)
    highlight_tint: int = Field(0, ge=0, le=360)
    highlight_tint_strength: int = Field(0, ge=0, le=100)
```

Add new models after `SuggestResponse`:

```python
# ── Reference image analysis ──────────────────────────────────────────

class ReferenceAnalyzeRequest(BaseModel):
    filename: str


class ReferenceAnalyzeResponse(BaseModel):
    params: CurrentParams
    curve_params: CurveParams
    style_name: str
    explanation: str


# ── Parameter preset library ──────────────────────────────────────────

class Preset(BaseModel):
    id: str
    name: str
    category: str = ""
    tags: List[str] = []
    params: CurrentParams
    curve_params: CurveParams
    created_at: str = ""
    updated_at: str = ""


class PresetCreate(BaseModel):
    name: str
    params: CurrentParams
    curve_params: CurveParams
    category: str = ""
    tags: List[str] = []


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[CurrentParams] = None
    curve_params: Optional[CurveParams] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_models.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add app/types/models.py tests/test_models.py
git commit -m "feat: extend data models for reference image and parameter presets"
```

---

## Task 3: Implement `preset_store.py`

**Files:**
- Create: `app/core/preset_store.py`
- Create: `tests/test_preset_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_preset_store.py`:

```python
import pytest
from app.core.preset_store import (
    create_preset, delete_preset, get_categories,
    get_preset, list_presets, update_preset,
)

_PARAMS = {
    "brightness": 10, "contrast": 5, "saturation": -10, "sharpness": 0,
    "color_temp": 20, "highlights": -30, "shadows": 20, "whites": 0,
    "blacks": 0, "vibrance": 15, "clarity": 10, "vignette": -20, "grain": 0,
    "shadow_tint": 0, "shadow_tint_strength": 0, "highlight_tint": 0,
    "highlight_tint_strength": 0, "smooth_skin": False, "smooth_level": 40,
    "brighten_skin": False, "background_action": "none",
}
_CURVES = {
    "rgb": [[0, 20], [255, 245]],
    "r": [[0, 0], [255, 255]],
    "g": [[0, 0], [255, 255]],
    "b": [[0, 8], [255, 255]],
}


def test_create_preset_returns_id_and_timestamps():
    item = create_preset("日系清透", _PARAMS, _CURVES, category="人像", tags=["日系"])
    assert "id" in item
    assert item["name"] == "日系清透"
    assert item["category"] == "人像"
    assert item["tags"] == ["日系"]
    assert "created_at" in item
    assert "updated_at" in item


def test_list_presets_returns_created():
    create_preset("胶片复古", _PARAMS, _CURVES)
    results = list_presets()
    assert any(p["name"] == "胶片复古" for p in results)


def test_list_presets_search_filter():
    create_preset("暖色电影", _PARAMS, _CURVES, tags=["电影"])
    create_preset("冷蓝风格", _PARAMS, _CURVES)
    results = list_presets(search="电影")
    assert all("电影" in p["name"] or "电影" in p.get("tags", []) for p in results)
    assert not any(p["name"] == "冷蓝风格" for p in results)


def test_list_presets_category_filter():
    create_preset("人像A", _PARAMS, _CURVES, category="人像")
    create_preset("风景B", _PARAMS, _CURVES, category="风景")
    results = list_presets(category="人像")
    assert all(p["category"] == "人像" for p in results)
    assert not any(p["name"] == "风景B" for p in results)


def test_get_categories():
    create_preset("X", _PARAMS, _CURVES, category="人像")
    create_preset("Y", _PARAMS, _CURVES, category="风景")
    cats = get_categories()
    assert "人像" in cats
    assert "风景" in cats


def test_get_preset_by_id():
    item = create_preset("测试", _PARAMS, _CURVES)
    found = get_preset(item["id"])
    assert found is not None
    assert found["id"] == item["id"]


def test_get_preset_unknown_returns_none():
    assert get_preset("nonexistent-id") is None


def test_update_preset_name():
    item = create_preset("旧名称", _PARAMS, _CURVES)
    updated = update_preset(item["id"], name="新名称")
    assert updated["name"] == "新名称"
    assert updated["updated_at"] >= item["updated_at"]


def test_update_preset_unknown_returns_none():
    assert update_preset("nonexistent-id", name="X") is None


def test_delete_preset_returns_true():
    item = create_preset("待删除", _PARAMS, _CURVES)
    assert delete_preset(item["id"]) is True
    assert get_preset(item["id"]) is None


def test_delete_preset_unknown_returns_false():
    assert delete_preset("nonexistent-id") is False


def test_list_sorted_by_updated_at_desc():
    a = create_preset("A", _PARAMS, _CURVES)
    b = create_preset("B", _PARAMS, _CURVES)
    results = list_presets()
    names = [p["name"] for p in results]
    assert names.index("B") < names.index("A")
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_preset_store.py -v
```

Expected: `ImportError` — `preset_store` module not found.

- [ ] **Step 3: Create `app/core/preset_store.py`**

```python
"""File-based parameter preset library.

Stores presets in data/presets.json as a flat JSON array.
Thread-safe for single-process usage.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DATA_FILE = Path("data/presets.json")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> List[dict]:
    if not DATA_FILE.exists():
        _save([])
    text = DATA_FILE.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else []


def _save(presets: List[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_presets(search: str = "", category: str = "") -> List[dict]:
    presets = _load()
    if search:
        q = search.lower()
        presets = [
            p for p in presets
            if q in p["name"].lower()
            or any(q in t.lower() for t in p.get("tags", []))
        ]
    if category:
        presets = [p for p in presets if p.get("category", "") == category]
    return sorted(presets, key=lambda p: p.get("updated_at", ""), reverse=True)


def get_categories() -> List[str]:
    return sorted({p.get("category", "") for p in _load() if p.get("category")})


def get_preset(preset_id: str) -> Optional[dict]:
    return next((p for p in _load() if p["id"] == preset_id), None)


def create_preset(
    name: str,
    params: dict,
    curve_params: dict,
    category: str = "",
    tags: List[str] = None,
) -> dict:
    presets = _load()
    now = _now()
    item = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "category": category.strip(),
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "params": params,
        "curve_params": curve_params,
        "created_at": now,
        "updated_at": now,
    }
    presets.append(item)
    _save(presets)
    return item


def update_preset(
    preset_id: str,
    name: Optional[str] = None,
    params: Optional[dict] = None,
    curve_params: Optional[dict] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[dict]:
    presets = _load()
    for i, p in enumerate(presets):
        if p["id"] == preset_id:
            if name is not None:
                p["name"] = name.strip()
            if params is not None:
                p["params"] = params
            if curve_params is not None:
                p["curve_params"] = curve_params
            if category is not None:
                p["category"] = category.strip()
            if tags is not None:
                p["tags"] = [t.strip() for t in tags if t.strip()]
            p["updated_at"] = _now()
            presets[i] = p
            _save(presets)
            return p
    return None


def delete_preset(preset_id: str) -> bool:
    presets = _load()
    filtered = [p for p in presets if p["id"] != preset_id]
    if len(filtered) < len(presets):
        _save(filtered)
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_preset_store.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```
git add app/core/preset_store.py tests/test_preset_store.py
git commit -m "feat: add parameter preset store"
```

---

## Task 4: Implement `reference_analyzer.py`

**Files:**
- Create: `app/core/reference_analyzer.py`
- Create: `tests/test_reference_analyzer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reference_analyzer.py`:

```python
import pytest
from app.core.reference_analyzer import _parse_and_normalize

_VALID_JSON = """{
  "brightness": 15, "contrast": -10, "highlights": -30, "shadows": 25,
  "whites": 0, "blacks": 5, "saturation": -20, "vibrance": 10,
  "clarity": 8, "sharpness": 5, "color_temp": 20, "vignette": -15,
  "grain": 10, "shadow_tint": 200, "shadow_tint_strength": 20,
  "highlight_tint": 45, "highlight_tint_strength": 15,
  "smooth_skin": true, "smooth_level": 60, "brighten_skin": false,
  "curve_params": {
    "rgb": [[0,20],[128,148],[255,245]],
    "r": [[0,5],[255,255]],
    "g": [[0,0],[255,255]],
    "b": [[0,8],[255,255]]
  },
  "style_name": "日系清透",
  "explanation": "整体偏亮，暗部提亮，色温偏暖，低对比，营造清透日系感"
}"""


def test_parse_valid_json():
    result = _parse_and_normalize(_VALID_JSON)
    assert result["brightness"] == 15
    assert result["shadows"] == 25
    assert result["style_name"] == "日系清透"
    assert result["curve_params"]["rgb"] == [[0, 20], [128, 148], [255, 245]]
    assert result["smooth_skin"] is True


def test_parse_clamps_out_of_range_values():
    json_str = '{"brightness": 999, "color_temp": -500, "grain": -10}'
    result = _parse_and_normalize(json_str)
    assert result["brightness"] == 60      # clamped to max
    assert result["color_temp"] == -100    # clamped to min
    assert result["grain"] == 0            # clamped to min


def test_parse_missing_fields_use_defaults():
    result = _parse_and_normalize('{"brightness": 20}')
    assert result["contrast"] == 0
    assert result["vibrance"] == 0
    assert result["curve_params"]["rgb"] == [[0, 0], [255, 255]]
    assert result["style_name"] == "参考风格"


def test_parse_invalid_json_returns_fallback():
    result = _parse_and_normalize("这不是JSON内容，模型出错了")
    assert result["brightness"] == 0
    assert result["style_name"] == "参考风格"
    assert "这不是JSON" in result["explanation"]


def test_parse_json_with_markdown_fences():
    text = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_and_normalize(text)
    assert result["brightness"] == 15
    assert result["style_name"] == "日系清透"


def test_parse_invalid_curve_points_fall_back_to_identity():
    json_str = '{"curve_params": {"rgb": "invalid", "r": [], "g": null, "b": [[0,0]]}}'
    result = _parse_and_normalize(json_str)
    assert result["curve_params"]["rgb"] == [[0, 0], [255, 255]]
    assert result["curve_params"]["r"] == [[0, 0], [255, 255]]


def test_parse_bool_fields():
    result = _parse_and_normalize('{"smooth_skin": true, "brighten_skin": false}')
    assert result["smooth_skin"] is True
    assert result["brighten_skin"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_reference_analyzer.py -v
```

Expected: `ImportError` — module not found.

- [ ] **Step 3: Create `app/core/reference_analyzer.py`**

```python
"""Reference image style analyzer using DashScope Qwen-VL.

Analyzes a reference photo and returns the slider parameters + curve control
points that characterize its visual style. The output dict maps directly to
CurrentParams + CurveParams fields.
"""

import json
import os
import re
from pathlib import Path

import dashscope
from dashscope import MultiModalConversation

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_SYSTEM = (
    "你是一位有十年经验的专业摄影师和调色师，精通 Lightroom、Photoshop 等修图工具。"
    "你的任务是：分析一张参考图的视觉风格，将其转化为可复现该风格的具体参数值。"
    "这些参数将被应用到另一张照片上，目标是让那张照片呈现出与参考图相近的视觉氛围。"
    "你必须做到：参数值具体、精准，能真正体现参考图的色调特征，不说套话，不给无意义的中性默认值。"
)

_PROMPT = """\
仔细观察这张参考图，从以下维度进行量化分析：

【曝光与亮度】
- 整体曝光水平：偏亮（日系清透）、偏暗（电影感）还是正常曝光？
- 暗部处理：阴影是否被提亮（灰雾/胶片感），还是压暗（强对比/黑位下沉）？
- 高光处理：高光是否有压制（保留细节）或轻微溢出倾向？

【对比度】
- 整体对比强弱：高对比（明暗分明）、中等，还是低对比（柔和/平淡）？
- 是否存在局部拉伸（暗部/亮部分别处理）？

【色彩】
- 饱和度：鲜艳（高饱和）、自然，还是偏灰/褪色（低饱和）？
- 色温：偏暖（金黄/琥珀）还是偏冷（蓝调/青冷）？
- 色偏：是否有明显色偏（偏绿、偏品红、偏青等）？
- 颜色分离：高光和阴影是否有不同色彩倾向（如高光暖+阴影冷的电影分色）？

【锐度与质感】
- 画面是锐利清晰，还是柔和/胶片颗粒感的朦胧？

基于以上分析，输出下面的 JSON（只输出 JSON，不含任何其他文字）：

━━ 参数说明 ━━
  brightness    整体亮度，-60~60，0=原图，正=更亮，负=更暗
  contrast      对比度，-60~60，正=更强，负=更柔
  highlights    高光控制，-100~100，负=压制高光，正=拉亮高光
  shadows       阴影控制，-100~100，正=提亮暗部，负=压暗
  whites        白点，-100~100，控制极亮区域
  blacks        黑点，-100~100，控制极暗区域
  saturation    饱和度，-60~60，正=鲜艳，负=去色/褪色
  vibrance      自然饱和度，-60~60，优先提升低饱和区域，保护肤色
  clarity       清晰度，-60~60，正=通透质感，负=柔焦奶油感
  sharpness     锐度，-60~60，正=更锐，负=更柔
  color_temp    色温，-100~100，负=冷蓝，正=暖黄
  vignette      暗角，-100~100，负=边缘压暗（电影感），正=边缘提亮
  grain         颗粒感，0~100，模拟胶片颗粒
  shadow_tint           阴影色相，0~360
  shadow_tint_strength  阴影色调强度，0~100
  highlight_tint        高光色相，0~360
  highlight_tint_strength 高光色调强度，0~100
  smooth_skin   磨皮开关，true/false（参考图有人像且皮肤明显柔化时开启）
  smooth_level  磨皮程度，0~100
  brighten_skin 提亮肤色，true/false

━━ 色彩曲线（curve_params）━━
控制点格式：[输入值, 输出值]，范围 0-255（整数）
必须包含 [0,Y0] 和 [255,Y255] 两个端点，中间可加 1-4 个控制点
  rgb   主曲线，控制整体明暗与对比
  r     红色通道（增大=偏红/暖，减小=偏青）
  g     绿色通道（增大=偏绿，减小=偏品红）
  b     蓝色通道（增大=偏蓝/冷，减小=偏黄）

━━ 规则 ━━
1. 参数必须真实反映图片，不要给无意义的中性值（如全部填 0）
2. 曲线是风格的核心，必须认真分析并给出有差异的控制点
3. brightness/highlights/shadows 等滑块和曲线可以同时使用，共同实现效果
4. style_name 要简洁有识别度（2-5字），explanation 要说清"为什么这么调"（30-60字）
5. 若图片色彩风格不明显，曲线可用直线，但滑块仍需如实填写

输出格式：
{
  "brightness": 整数,
  "contrast": 整数,
  "highlights": 整数,
  "shadows": 整数,
  "whites": 整数,
  "blacks": 整数,
  "saturation": 整数,
  "vibrance": 整数,
  "clarity": 整数,
  "sharpness": 整数,
  "color_temp": 整数,
  "vignette": 整数,
  "grain": 整数,
  "shadow_tint": 整数,
  "shadow_tint_strength": 整数,
  "highlight_tint": 整数,
  "highlight_tint_strength": 整数,
  "smooth_skin": bool,
  "smooth_level": 整数,
  "brighten_skin": bool,
  "curve_params": {
    "rgb": [[整数,整数], ...],
    "r":   [[整数,整数], ...],
    "g":   [[整数,整数], ...],
    "b":   [[整数,整数], ...]
  },
  "style_name": "字符串",
  "explanation": "字符串"
}"""

_INT_FIELDS_CLAMP = {
    "brightness": (-60, 60),
    "contrast": (-60, 60),
    "highlights": (-100, 100),
    "shadows": (-100, 100),
    "whites": (-100, 100),
    "blacks": (-100, 100),
    "saturation": (-60, 60),
    "vibrance": (-60, 60),
    "clarity": (-60, 60),
    "sharpness": (-60, 60),
    "color_temp": (-100, 100),
    "vignette": (-100, 100),
    "grain": (0, 100),
    "shadow_tint": (0, 360),
    "shadow_tint_strength": (0, 100),
    "highlight_tint": (0, 360),
    "highlight_tint_strength": (0, 100),
    "smooth_level": (0, 100),
}

_IDENTITY_CURVE = [[0, 0], [255, 255]]
_IDENTITY_CURVES = {"rgb": _IDENTITY_CURVE, "r": _IDENTITY_CURVE, "g": _IDENTITY_CURVE, "b": _IDENTITY_CURVE}


def _file_uri(file_path: Path) -> str:
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"file://{abs_path}"


def _image_ref(file_path: Path) -> str:
    if os.getenv("USE_BASE64", "").lower() in ("1", "true"):
        from app.core.image_gen import _encode_file
        return _encode_file(file_path)
    return _file_uri(file_path)


def _extract_text(rsp) -> str:
    choices = rsp.output.choices
    if not choices:
        return ""
    choice = choices[0]
    try:
        content = choice["message"]["content"]
    except TypeError:
        content = choice.message.content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("text")
        )
    return str(content)


def _parse_and_normalize(text: str) -> dict:
    """Parse model output and normalize to a valid parameter dict.

    Always returns a complete dict — falls back to neutral values on any
    parse failure so the caller never needs to handle a partial result.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    try:
        raw = json.loads(match.group() if match else cleaned)
    except (json.JSONDecodeError, AttributeError):
        return {
            **{k: 0 for k in _INT_FIELDS_CLAMP},
            "smooth_skin": False,
            "brighten_skin": False,
            "curve_params": _IDENTITY_CURVES,
            "style_name": "参考风格",
            "explanation": text[:200].strip(),
        }

    result: dict = {}

    for field, (lo, hi) in _INT_FIELDS_CLAMP.items():
        val = raw.get(field, 0)
        try:
            result[field] = max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            result[field] = 0

    result["smooth_skin"] = bool(raw.get("smooth_skin", False))
    result["brighten_skin"] = bool(raw.get("brighten_skin", False))

    raw_curves = raw.get("curve_params") or {}
    curves: dict = {}
    for ch in ("rgb", "r", "g", "b"):
        pts = raw_curves.get(ch) if isinstance(raw_curves, dict) else None
        if not isinstance(pts, list) or len(pts) < 2:
            curves[ch] = list(_IDENTITY_CURVE)
        else:
            try:
                curves[ch] = [
                    [max(0, min(255, int(p[0]))), max(0, min(255, int(p[1])))]
                    for p in pts if len(p) >= 2
                ]
                if len(curves[ch]) < 2:
                    curves[ch] = list(_IDENTITY_CURVE)
            except (TypeError, ValueError):
                curves[ch] = list(_IDENTITY_CURVE)
    result["curve_params"] = curves

    result["style_name"] = str(raw.get("style_name", "")).strip() or "参考风格"
    result["explanation"] = str(raw.get("explanation", "")).strip()

    return result


def analyze_reference(image_path: Path) -> dict:
    """Analyze a reference image and return its style as a parameter dict.

    Returns:
        dict with all CurrentParams fields + curve_params + style_name + explanation.
    Raises:
        ValueError: DASHSCOPE_API_KEY not set.
        RuntimeError: API call failed or empty response.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未配置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")

    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": [{"text": _SYSTEM}]},
            {"role": "user", "content": [
                {"image": _image_ref(Path(image_path))},
                {"text": _PROMPT},
            ]},
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"参考图分析失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("模型返回内容为空")

    return _parse_and_normalize(text)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_reference_analyzer.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add app/core/reference_analyzer.py tests/test_reference_analyzer.py
git commit -m "feat: add reference image analyzer with Qwen-VL"
```

---

## Task 5: Extend `image_processor.py`

**Files:**
- Modify: `app/core/image_processor.py`
- Create: `tests/test_image_processor_extended.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_image_processor_extended.py`:

```python
import numpy as np
import pytest
from PIL import Image
from app.core.image_processor import apply_extended_edits
from app.types.models import ExtendedEditParams


def _solid(r, g, b, size=100) -> Image.Image:
    return Image.new("RGB", (size, size), (r, g, b))


def test_identity_returns_same_image():
    img = _solid(120, 80, 60)
    result = apply_extended_edits(img, ExtendedEditParams())
    assert np.array_equal(np.array(img), np.array(result))


def test_highlights_darkens_bright_pixels():
    img = _solid(220, 220, 220)  # bright
    result = apply_extended_edits(img, ExtendedEditParams(highlights=-50))
    arr_in = np.array(img).mean()
    arr_out = np.array(result).mean()
    assert arr_out < arr_in


def test_shadows_brightens_dark_pixels():
    img = _solid(40, 40, 40)  # dark
    result = apply_extended_edits(img, ExtendedEditParams(shadows=50))
    arr_in = np.array(img).mean()
    arr_out = np.array(result).mean()
    assert arr_out > arr_in


def test_blacks_raises_black_point():
    img = _solid(10, 10, 10)  # near-black
    result = apply_extended_edits(img, ExtendedEditParams(blacks=50))
    assert np.array(result).mean() > np.array(img).mean()


def test_whites_lowers_white_point():
    img = _solid(240, 240, 240)  # near-white
    result = apply_extended_edits(img, ExtendedEditParams(whites=-50))
    assert np.array(result).mean() < np.array(img).mean()


def test_vibrance_increases_saturation():
    img = _solid(150, 120, 100)  # low saturation
    result = apply_extended_edits(img, ExtendedEditParams(vibrance=40))
    in_arr = np.array(img).astype(float)
    out_arr = np.array(result).astype(float)
    in_sat = in_arr.max(axis=2) - in_arr.min(axis=2)
    out_sat = out_arr.max(axis=2) - out_arr.min(axis=2)
    assert out_sat.mean() > in_sat.mean()


def test_clarity_positive_increases_contrast():
    # Clarity boosts local contrast — edge difference should increase
    arr = np.tile(np.linspace(50, 200, 100, dtype=np.uint8), (100, 1))
    img = Image.fromarray(np.stack([arr, arr, arr], axis=2))
    result = apply_extended_edits(img, ExtendedEditParams(clarity=40))
    in_std = np.array(img).std()
    out_std = np.array(result).std()
    assert out_std >= in_std


def test_vignette_negative_darkens_corners():
    img = _solid(200, 200, 200, size=200)
    result = apply_extended_edits(img, ExtendedEditParams(vignette=-80))
    arr = np.array(result).astype(float)
    center = arr[90:110, 90:110].mean()
    corner = arr[0:20, 0:20].mean()
    assert corner < center


def test_vignette_positive_brightens_corners():
    img = _solid(100, 100, 100, size=200)
    result = apply_extended_edits(img, ExtendedEditParams(vignette=80))
    arr = np.array(result).astype(float)
    center = arr[90:110, 90:110].mean()
    corner = arr[0:20, 0:20].mean()
    assert corner > center


def test_grain_changes_pixel_values():
    img = _solid(128, 128, 128)
    result = apply_extended_edits(img, ExtendedEditParams(grain=50))
    assert not np.array_equal(np.array(img), np.array(result))


def test_split_toning_shadow_shifts_dark_pixels():
    img = _solid(30, 30, 30)  # dark image
    result = apply_extended_edits(
        img, ExtendedEditParams(shadow_tint=240, shadow_tint_strength=80)
    )
    assert not np.array_equal(np.array(img), np.array(result))
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_image_processor_extended.py -v
```

Expected: `ImportError` — `apply_extended_edits` not found.

- [ ] **Step 3: Implement `apply_extended_edits` in `app/core/image_processor.py`**

Add the following to the end of `app/core/image_processor.py` (keep all existing code intact):

```python
import colorsys
import cv2

from app.types.models import ExtendedEditParams


def apply_extended_edits(img: Image.Image, params: ExtendedEditParams) -> Image.Image:
    """Apply extended tonal and style adjustments."""
    if _is_identity_extended(params):
        return img

    img = img.convert("RGB")
    arr = np.array(img, dtype=np.float32)

    if any(v != 0 for v in [params.highlights, params.shadows, params.whites, params.blacks]):
        arr = _adjust_tonal_range(arr, params.highlights, params.shadows, params.whites, params.blacks)

    if params.vibrance != 0:
        arr = _adjust_vibrance(arr, params.vibrance)

    if params.clarity != 0:
        arr = _adjust_clarity(arr, params.clarity)

    if params.shadow_tint_strength > 0 or params.highlight_tint_strength > 0:
        arr = _apply_split_toning(
            arr,
            params.shadow_tint, params.shadow_tint_strength,
            params.highlight_tint, params.highlight_tint_strength,
        )

    img = Image.fromarray(arr.astype(np.uint8))

    if params.vignette != 0:
        img = _apply_vignette(img, params.vignette)

    if params.grain > 0:
        img = _apply_grain(img, params.grain)

    return img


def _is_identity_extended(params: ExtendedEditParams) -> bool:
    return all([
        params.highlights == 0, params.shadows == 0,
        params.whites == 0, params.blacks == 0,
        params.vibrance == 0, params.clarity == 0,
        params.vignette == 0, params.grain == 0,
        params.shadow_tint_strength == 0, params.highlight_tint_strength == 0,
    ])


def _adjust_tonal_range(
    arr: np.ndarray, highlights: int, shadows: int, whites: int, blacks: int
) -> np.ndarray:
    """Apply per-zone tonal adjustments via a 256-entry LUT."""
    lut = np.arange(256, dtype=np.float32)

    if blacks != 0:
        mask = np.clip((64.0 - lut) / 64.0, 0, 1) ** 2
        lut += blacks * 0.5 * mask

    if shadows != 0:
        mask = np.clip((128.0 - lut) / 128.0, 0, 1)
        lut += shadows * 0.4 * mask

    if highlights != 0:
        mask = np.clip((lut - 128.0) / 127.0, 0, 1)
        lut += highlights * 0.4 * mask

    if whites != 0:
        mask = np.clip((lut - 192.0) / 63.0, 0, 1) ** 2
        lut += whites * 0.5 * mask

    lut = lut.clip(0, 255).astype(np.uint8)
    return lut[arr.astype(np.uint8)].astype(np.float32)


def _adjust_vibrance(arr: np.ndarray, vibrance: int) -> np.ndarray:
    """Boost low-saturation pixels more than already-vivid ones."""
    img_uint8 = arr.astype(np.uint8)
    hsv = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = hsv[:, :, 1] / 255.0
    factor = vibrance / 60.0
    delta = factor * (1.0 - sat) * 255.0
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] + delta, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)


def _adjust_clarity(arr: np.ndarray, clarity: int) -> np.ndarray:
    """Midtone contrast boost (positive) or softening (negative)."""
    img_uint8 = arr.astype(np.uint8)
    if clarity > 0:
        blurred = cv2.GaussianBlur(img_uint8, (0, 0), 10)
        alpha = clarity / 60.0 * 0.5
        result = cv2.addWeighted(img_uint8, 1 + alpha, blurred, -alpha, 0)
    else:
        sigma = abs(clarity) / 60.0 * 3.0
        ksize = max(3, int(sigma * 3) | 1)
        result = cv2.GaussianBlur(img_uint8, (ksize, ksize), sigma)
    return result.astype(np.float32)


def _apply_vignette(img: Image.Image, vignette: int) -> Image.Image:
    """Darken (negative) or brighten (positive) image edges radially."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - w / 2.0) / (w / 2.0)) ** 2 + ((Y - h / 2.0) / (h / 2.0)) ** 2)
    center_mask = np.clip(1.0 - dist, 0, 1) ** 2
    factor = vignette / 100.0
    blend = (1.0 + factor * (1.0 - center_mask))[:, :, np.newaxis]
    return Image.fromarray(np.clip(arr * blend, 0, 255).astype(np.uint8))


def _apply_grain(img: Image.Image, grain: int) -> Image.Image:
    """Overlay luminance noise to simulate film grain."""
    arr = np.array(img, dtype=np.float32)
    sigma = grain / 100.0 * 20.0
    noise = np.random.normal(0, sigma, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def _apply_split_toning(
    arr: np.ndarray,
    shadow_hue: int, shadow_strength: int,
    highlight_hue: int, highlight_strength: int,
) -> np.ndarray:
    """Tint shadows and highlights with independent hue colors."""
    luma = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0
    result = arr.copy()

    if shadow_strength > 0:
        s_mask = np.clip(1.0 - luma * 2, 0, 1)[:, :, np.newaxis] * (shadow_strength / 100.0) * 0.25
        color = np.array(colorsys.hsv_to_rgb(shadow_hue / 360.0, 1.0, 1.0)) * 255.0
        result = result * (1 - s_mask) + color * s_mask

    if highlight_strength > 0:
        h_mask = np.clip((luma - 0.5) * 2, 0, 1)[:, :, np.newaxis] * (highlight_strength / 100.0) * 0.25
        color = np.array(colorsys.hsv_to_rgb(highlight_hue / 360.0, 1.0, 1.0)) * 255.0
        result = result * (1 - h_mask) + color * h_mask

    return np.clip(result, 0, 255)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_image_processor_extended.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```
git add app/core/image_processor.py tests/test_image_processor_extended.py
git commit -m "feat: add extended image processing (highlights/shadows/vibrance/clarity/vignette/grain/split-toning)"
```

---

## Task 6: Add API Routes + Update `main.py`

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/main.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_routes.py`:

```python
import io
import json
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)

_CURVE = [[0, 0], [255, 255]]
_PRESET_PAYLOAD = {
    "name": "日系清透",
    "category": "人像",
    "tags": ["日系"],
    "params": {
        "brightness": 15, "contrast": -10, "saturation": -20, "sharpness": 5,
        "color_temp": 20, "smooth_skin": False, "smooth_level": 40,
        "brighten_skin": False, "background_action": "none",
        "highlights": -30, "shadows": 25, "whites": 0, "blacks": 5,
        "vibrance": 10, "clarity": 8, "vignette": -15, "grain": 10,
        "shadow_tint": 0, "shadow_tint_strength": 0,
        "highlight_tint": 0, "highlight_tint_strength": 0,
    },
    "curve_params": {"rgb": _CURVE, "r": _CURVE, "g": _CURVE, "b": _CURVE},
}


def _upload_image() -> str:
    """Upload a test image and return filename."""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (120, 80, 60)).save(buf, "JPEG")
    buf.seek(0)
    res = client.post("/api/upload", files={"file": ("test.jpg", buf, "image/jpeg")})
    assert res.status_code == 200
    return res.json()["filename"]


# ── Preset CRUD ───────────────────────────────────────────────────────

def test_create_preset():
    res = client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "日系清透"
    assert "id" in data


def test_list_presets():
    client.post("/api/presets", json=_PRESET_PAYLOAD)
    res = client.get("/api/presets")
    assert res.status_code == 200
    assert "presets" in res.json()
    assert "categories" in res.json()


def test_list_presets_search():
    client.post("/api/presets", json=_PRESET_PAYLOAD)
    res = client.get("/api/presets?search=日系")
    assert res.status_code == 200
    assert any(p["name"] == "日系清透" for p in res.json()["presets"])


def test_update_preset():
    create_res = client.post("/api/presets", json=_PRESET_PAYLOAD)
    preset_id = create_res.json()["id"]
    update_res = client.put(f"/api/presets/{preset_id}", json={"name": "更新后名称"})
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "更新后名称"


def test_update_preset_not_found():
    res = client.put("/api/presets/nonexistent-id", json={"name": "X"})
    assert res.status_code == 404


def test_delete_preset():
    create_res = client.post("/api/presets", json=_PRESET_PAYLOAD)
    preset_id = create_res.json()["id"]
    del_res = client.delete(f"/api/presets/{preset_id}")
    assert del_res.status_code == 200
    assert del_res.json() == {"ok": True}


def test_delete_preset_not_found():
    res = client.delete("/api/presets/nonexistent-id")
    assert res.status_code == 404


# ── Analyze reference ─────────────────────────────────────────────────

def test_analyze_reference_file_not_found():
    res = client.post("/api/analyze-reference", json={"filename": "does_not_exist.jpg"})
    assert res.status_code == 404


def test_analyze_reference_success():
    filename = _upload_image()
    mock_result = {
        "brightness": 15, "contrast": -10, "highlights": -30, "shadows": 25,
        "whites": 0, "blacks": 5, "saturation": -20, "vibrance": 10,
        "clarity": 8, "sharpness": 5, "color_temp": 20, "vignette": -15,
        "grain": 10, "shadow_tint": 0, "shadow_tint_strength": 0,
        "highlight_tint": 0, "highlight_tint_strength": 0,
        "smooth_skin": False, "smooth_level": 40, "brighten_skin": False,
        "curve_params": {"rgb": _CURVE, "r": _CURVE, "g": _CURVE, "b": _CURVE},
        "style_name": "日系清透",
        "explanation": "整体偏亮，色温偏暖",
    }
    with patch("app.api.routes.analyze_reference", return_value=mock_result):
        res = client.post("/api/analyze-reference", json={"filename": filename})
    assert res.status_code == 200
    data = res.json()
    assert data["style_name"] == "日系清透"
    assert data["params"]["brightness"] == 15
    assert data["curve_params"]["rgb"] == _CURVE


# ── Manual edit with extended params ─────────────────────────────────

def test_manual_edit_with_extended_params():
    filename = _upload_image()
    payload = {
        "filename": filename,
        "edit_params": {"brightness": 1.0, "contrast": 1.0, "saturation": 1.0, "sharpness": 1.0, "color_temp": 0},
        "extended_params": {"vignette": -50, "grain": 20, "highlights": -20, "shadows": 10,
                            "whites": 0, "blacks": 0, "vibrance": 0, "clarity": 0,
                            "shadow_tint": 0, "shadow_tint_strength": 0,
                            "highlight_tint": 0, "highlight_tint_strength": 0},
    }
    res = client.post("/api/edit/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_routes.py -v
```

Expected: failures on preset routes (endpoints not defined) and analyze-reference route (not defined).

- [ ] **Step 3: Update `app/main.py`**

Add `Path("data").mkdir(exist_ok=True)` after the existing mkdir calls:

```python
Path("uploads").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)
```

- [ ] **Step 4: Add new routes to `app/api/routes.py`**

Add these imports at the top of `routes.py`:

```python
from app.core.preset_store import (
    create_preset as _create_preset,
    delete_preset as _delete_preset,
    get_categories as _get_preset_categories,
    get_preset,
    list_presets,
    update_preset as _update_preset,
)
from app.core.reference_analyzer import analyze_reference
from app.types.models import (
    AIEditRequest, AnalyzeRequest, AnalyzeResponse,
    CurrentParams, CurveParams, EditResponse,
    ExtendedEditParams,
    ManualEditRequest, Preset, PresetCreate, PresetUpdate,
    Prompt, PromptCreate, PromptUpdate,
    ReferenceAnalyzeRequest, ReferenceAnalyzeResponse,
    StyleSuggestion, SuggestRequest, SuggestResponse,
)
```

Also add to the `apply_extended_edits` import in routes.py:

```python
from app.core.image_processor import apply_basic_edits, apply_extended_edits
```

Update the `/api/edit/manual` handler to call `apply_extended_edits` after `apply_basic_edits`:

```python
@router.post("/edit/manual", response_model=EditResponse)
async def manual_edit(request: ManualEditRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        with Image.open(src) as img:
            result = img.convert("RGB")
            result = apply_basic_edits(result, request.edit_params)
            result = apply_extended_edits(result, request.extended_params)
            result = apply_portrait(result, request.portrait_params)
            result = apply_background(result, request.background_params)
            result = apply_curves(result, request.curve_params)

            out_name = f"edited_{uuid.uuid4().hex[:10]}.jpg"
            out_path = OUTPUT_DIR / out_name

            if result.mode == "RGBA":
                out_name = out_name.replace(".jpg", ".png")
                out_path = OUTPUT_DIR / out_name
                result.save(out_path, "PNG")
            else:
                result.save(out_path, "JPEG", quality=92, optimize=True)

        return EditResponse(success=True, result_filename=out_name)
    except Exception as e:
        raise HTTPException(500, f"处理失败：{e}")
```

Add new route handlers at the end of `routes.py`:

```python
# ── Reference image analysis ──────────────────────────────────────────

@router.post("/analyze-reference", response_model=ReferenceAnalyzeResponse)
async def analyze_reference_image(request: ReferenceAnalyzeRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        raw = await asyncio.to_thread(analyze_reference, src)

        params_dict = {k: v for k, v in raw.items()
                       if k not in ("curve_params", "style_name", "explanation")}
        curve_dict = raw.get("curve_params", {})

        return ReferenceAnalyzeResponse(
            params=CurrentParams(**params_dict),
            curve_params=CurveParams(**curve_dict),
            style_name=raw.get("style_name", "参考风格"),
            explanation=raw.get("explanation", ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"参考图分析失败：{e}")


# ── Parameter preset library ──────────────────────────────────────────

@router.get("/presets")
async def presets_list(search: str = "", category: str = ""):
    return {
        "presets": list_presets(search, category),
        "categories": _get_preset_categories(),
    }


@router.post("/presets", response_model=Preset)
async def presets_create(data: PresetCreate):
    if not data.name.strip():
        raise HTTPException(400, "名称不能为空")
    return _create_preset(
        data.name,
        data.params.model_dump(),
        data.curve_params.model_dump(),
        data.category,
        data.tags,
    )


@router.put("/presets/{preset_id}", response_model=Preset)
async def presets_update(preset_id: str, data: PresetUpdate):
    item = _update_preset(
        preset_id,
        name=data.name,
        params=data.params.model_dump() if data.params else None,
        curve_params=data.curve_params.model_dump() if data.curve_params else None,
        category=data.category,
        tags=data.tags,
    )
    if item is None:
        raise HTTPException(404, "预设不存在")
    return item


@router.delete("/presets/{preset_id}")
async def presets_delete(preset_id: str):
    if not _delete_preset(preset_id):
        raise HTTPException(404, "预设不存在")
    return {"ok": True}
```

- [ ] **Step 5: Run all tests to verify they pass**

```
pytest tests/ -v
```

Expected: all tests PASS. If any fail, check import paths and that `apply_extended_edits` is exported from `image_processor.py`.

- [ ] **Step 6: Commit**

```
git add app/main.py app/api/routes.py tests/test_routes.py
git commit -m "feat: add /api/analyze-reference and /api/presets endpoints"
```

---

## Task 7: Final Smoke Test

- [ ] **Step 1: Run full test suite**

```
pytest tests/ -v --tb=short
```

Expected: all tests PASS, no warnings about missing fixtures.

- [ ] **Step 2: Start server and verify endpoints are reachable**

```
uvicorn app.main:app --reload --port 8000
```

Then in another terminal:

```
curl -X GET http://localhost:8000/api/presets
```

Expected: `{"presets": [], "categories": []}` with status 200.

- [ ] **Step 3: Final commit**

```
git add -A
git commit -m "feat: reference image style extraction + parameter preset library (backend)"
```
