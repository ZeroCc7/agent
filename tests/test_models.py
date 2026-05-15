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
