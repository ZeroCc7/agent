from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, computed_field, Field


class EditParams(BaseModel):
    brightness: float = Field(1.0, ge=0.1, le=3.0)
    contrast: float = Field(1.0, ge=0.1, le=3.0)
    saturation: float = Field(1.0, ge=0.0, le=3.0)
    sharpness: float = Field(1.0, ge=0.0, le=3.0)
    color_temp: int = Field(0, ge=-100, le=100)


class PortraitParams(BaseModel):
    smooth_skin: bool = False
    smooth_level: float = Field(0.5, ge=0.0, le=1.0)
    brighten_skin: bool = False
    brighten_level: float = Field(0.2, ge=0.0, le=1.0)


class BackgroundParams(BaseModel):
    action: Literal["none", "blur", "remove"] = "none"
    blur_radius: int = Field(15, ge=1, le=50)


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


class CurveParams(BaseModel):
    rgb: List[List[int]] = Field(default_factory=lambda: [[0, 0], [255, 255]])
    r:   List[List[int]] = Field(default_factory=lambda: [[0, 0], [255, 255]])
    g:   List[List[int]] = Field(default_factory=lambda: [[0, 0], [255, 255]])
    b:   List[List[int]] = Field(default_factory=lambda: [[0, 0], [255, 255]])


class ManualEditRequest(BaseModel):
    filename: str
    edit_params: EditParams = EditParams()
    portrait_params: PortraitParams = PortraitParams()
    background_params: BackgroundParams = BackgroundParams()
    curve_params: CurveParams = Field(default_factory=CurveParams)
    extended_params: ExtendedEditParams = Field(default_factory=ExtendedEditParams)


class AIEditRequest(BaseModel):
    filename: str
    instruction: str


class EditResponse(BaseModel):
    success: bool
    result_filename: str = ""
    message: str = ""
    ai_explanation: str = ""


class StyleSuggestion(BaseModel):
    style: str
    description: str
    prompt: str


class AnalyzeRequest(BaseModel):
    filename: str


class AnalyzeResponse(BaseModel):
    suggestions: List[StyleSuggestion]


# ── Prompt library ────────────────────────────────────────────────────

class Prompt(BaseModel):
    id: str
    name: str
    category: str = ""
    tags: List[str] = []
    prompt: str
    created_at: str = ""
    updated_at: str = ""


class PromptCreate(BaseModel):
    name: str
    prompt: str
    category: str = ""
    tags: List[str] = []


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


# ── Parameter advisor ─────────────────────────────────────────────────

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


class SuggestRequest(BaseModel):
    instruction: str
    current_params: CurrentParams = CurrentParams()


class SuggestResponse(BaseModel):
    params: CurrentParams
    explanation: str = ""
    curve_params: Optional[CurveParams] = None


# ── Reference image analysis ──────────────────────────────────────────

class ReferenceAnalyzeRequest(BaseModel):
    filename: str


class ReferenceAnalyzeResponse(BaseModel):
    params: CurrentParams
    curve_params: CurveParams
    style_name: str
    explanation: str


class CompareStyleRequest(BaseModel):
    result_filename: str
    reference_filename: str


class CompareStyleResponse(BaseModel):
    params: CurrentParams
    curve_params: CurveParams
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


# ── Agent loop ────────────────────────────────────────────────────────

class AgentEditOutput(BaseModel):
    """Parameters output by EditingAgent — fed directly into the apply pipeline."""
    edit_params: EditParams = Field(default_factory=EditParams)
    extended_params: ExtendedEditParams = Field(default_factory=ExtendedEditParams)
    portrait_params: PortraitParams = Field(default_factory=PortraitParams)
    background_params: BackgroundParams = Field(default_factory=BackgroundParams)
    curve_params: CurveParams = Field(default_factory=CurveParams)
    explanation: str = ""


class ReviewScore(BaseModel):
    visual_quality: float = Field(ge=0, le=10)
    instruction_match: float = Field(ge=0, le=10)
    reference_match: Optional[float] = Field(None, ge=0, le=10)
    suggestions: Dict[str, str] = Field(default_factory=dict)

    @computed_field
    @property
    def overall(self) -> float:
        if self.reference_match is not None:
            return (
                self.visual_quality * 0.25
                + self.instruction_match * 0.40
                + self.reference_match * 0.35
            )
        return self.visual_quality * 0.35 + self.instruction_match * 0.65

    @computed_field
    @property
    def is_satisfied(self) -> bool:
        return self.overall >= 8.0


class AgentIteration(BaseModel):
    round: int
    image_filename: str
    params: AgentEditOutput
    scores: dict  # keys: visual_quality, instruction_match, reference_match, overall
    suggestions: dict
    is_satisfied: bool


class AgentSession(BaseModel):
    session_id: str
    instruction: str
    created_at: str
    has_reference: bool
    iterations: List[AgentIteration] = []
    best_round: int = 0


class AgentEditRequest(BaseModel):
    filename: str
    instruction: str
    reference_filename: Optional[str] = None
