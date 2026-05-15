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
