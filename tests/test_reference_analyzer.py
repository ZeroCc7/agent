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
    assert result["brightness"] == 60
    assert result["color_temp"] == -100
    assert result["grain"] == 0


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
