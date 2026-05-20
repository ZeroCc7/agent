import base64
import io
import json
import os
from typing import Optional

import anthropic
from PIL import Image

from app.types.models import (
    AgentEditOutput, BackgroundParams, CurveParams,
    EditParams, ExtendedEditParams, PortraitParams, ReviewScore,
)

_SYSTEM_FIRST = """You are an expert photo retouching assistant. Analyze the image(s) and instruction, then return ONLY a valid JSON object.

Return exactly this structure:
{
  "edit_params": {
    "brightness": <float 0.5-2.0, 1.0=unchanged>,
    "contrast": <float 0.5-2.0, 1.0=unchanged>,
    "saturation": <float 0.5-2.0, 1.0=unchanged>,
    "sharpness": <float 0.5-2.0, 1.0=unchanged>,
    "color_temp": <int -100 to 100, 0=neutral, positive=warm, negative=cool>
  },
  "extended_params": {
    "highlights": <int -100 to 100>,
    "shadows": <int -100 to 100>,
    "whites": <int -100 to 100>,
    "blacks": <int -100 to 100>,
    "vibrance": <int -60 to 60>,
    "clarity": <int -60 to 60>,
    "vignette": <int -100 to 100>,
    "grain": <int 0 to 100>,
    "shadow_tint": <int 0 to 360>,
    "shadow_tint_strength": <int 0 to 100>,
    "highlight_tint": <int 0 to 360>,
    "highlight_tint_strength": <int 0 to 100>
  },
  "portrait_params": {
    "smooth_skin": <bool>,
    "smooth_level": <float 0.0-1.0>,
    "brighten_skin": <bool>,
    "brighten_level": <float 0.0-1.0>
  },
  "background_params": {
    "action": <"none"|"blur"|"remove">,
    "blur_radius": <int 5-30>
  },
  "curve_params": {
    "rgb": [[0,0],[255,255]],
    "r": [[0,0],[255,255]],
    "g": [[0,0],[255,255]],
    "b": [[0,0],[255,255]]
  },
  "explanation": "<one sentence in Chinese explaining what you changed>"
}

Keep edits natural and subtle. Output JSON only."""

_SYSTEM_FEEDBACK = """You are an expert photo retouching assistant refining a previous edit based on reviewer feedback.

Adjust ONLY the parameters flagged as problematic. Do not change dimensions that were already rated well (score >= 8).

Return the same JSON structure with your refined parameters. Output JSON only."""


def _img_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def _parse(text: str) -> AgentEditOutput:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    data = json.loads(text)
    return AgentEditOutput(
        edit_params=EditParams(**data.get("edit_params", {})),
        extended_params=ExtendedEditParams(**data.get("extended_params", {})),
        portrait_params=PortraitParams(**data.get("portrait_params", {})),
        background_params=BackgroundParams(**data.get("background_params", {})),
        curve_params=CurveParams(**data.get("curve_params", {})),
        explanation=data.get("explanation", ""),
    )


def run_editing_agent(
    original_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
    previous_output: Optional[AgentEditOutput] = None,
    review_score: Optional[ReviewScore] = None,
) -> AgentEditOutput:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)
    is_first = previous_output is None

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(original_img)}},
        {"type": "text", "text": "原始图片"},
    ]

    if reference_img is not None:
        content += [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(reference_img)}},
            {"type": "text", "text": "参考图片（请让效果尽量接近此风格）"},
        ]

    if is_first:
        user_text = f"用户指令：{instruction}"
    else:
        sugg_lines = "\n".join(f"  - {k}: {v}" for k, v in (review_score.suggestions if review_score else {}).items())
        user_text = (
            f"用户指令：{instruction}\n\n"
            f"上一轮参数：\n{previous_output.model_dump_json(indent=2)}\n\n"
            f"审查反馈（请针对以下问题调整，不要大幅改动已合格的维度）：\n{sugg_lines}"
        )

    content.append({"type": "text", "text": user_text})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM_FIRST if is_first else _SYSTEM_FEEDBACK,
        messages=[{"role": "user", "content": content}],
    )
    return _parse(response.content[0].text)
