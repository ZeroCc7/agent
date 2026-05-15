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
