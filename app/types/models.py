from typing import List, Literal, Optional
from pydantic import BaseModel, Field


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


class SuggestRequest(BaseModel):
    instruction: str
    current_params: CurrentParams = CurrentParams()


class SuggestResponse(BaseModel):
    params: CurrentParams
    explanation: str = ""
    curve_params: Optional[CurveParams] = None
