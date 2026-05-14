from typing import Literal
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


class ManualEditRequest(BaseModel):
    filename: str
    edit_params: EditParams = EditParams()
    portrait_params: PortraitParams = PortraitParams()
    background_params: BackgroundParams = BackgroundParams()


class AIEditRequest(BaseModel):
    filename: str
    instruction: str


class EditResponse(BaseModel):
    success: bool
    result_filename: str = ""
    message: str = ""
    ai_explanation: str = ""
