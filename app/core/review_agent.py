import base64
import io
import json
import os
from typing import Optional

import anthropic
from PIL import Image

from app.types.models import ReviewScore

_SYSTEM = """You are a professional photo quality reviewer. Compare the photos provided and score the edit.

Return ONLY a valid JSON object:
{
  "scores": {
    "visual_quality": <float 0-10>,
    "instruction_match": <float 0-10>,
    "reference_match": <float 0-10 or null if no reference>
  },
  "suggestions": {
    "visual_quality": "<specific fix in Chinese, or empty string if score >= 8>",
    "instruction_match": "<specific fix in Chinese, or empty string if score >= 8>",
    "reference_match": "<specific fix in Chinese, or empty string if no reference or score >= 8>"
  }
}

Scoring criteria:
- visual_quality: Is the result natural? No overexposure, color cast, halos, or artifacts?
- instruction_match: Did the edit accomplish what the user instruction asked for?
- reference_match: How closely does the edit's style match the reference image? (null if no reference provided)

Be specific in suggestions — name the exact parameter to adjust and the direction.
Output JSON only."""


def _img_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def run_review_agent(
    original_img: Image.Image,
    edited_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
    round_num: int = 1,
) -> ReviewScore:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(original_img)}},
        {"type": "text", "text": "原始图片"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(edited_img)}},
        {"type": "text", "text": f"第{round_num}轮修图结果"},
    ]

    if reference_img is not None:
        content += [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(reference_img)}},
            {"type": "text", "text": "参考图片（目标风格）"},
        ]

    content.append({"type": "text", "text": f"用户指令：{instruction}\n\n请评分并给出改进建议。"})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )

    text = response.content[0].text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

    data = json.loads(text)
    scores = data.get("scores", {})
    suggestions = {k: v for k, v in data.get("suggestions", {}).items() if v}

    ref_raw = scores.get("reference_match")
    return ReviewScore(
        visual_quality=float(scores.get("visual_quality", 5.0)),
        instruction_match=float(scores.get("instruction_match", 5.0)),
        reference_match=float(ref_raw) if ref_raw is not None else None,
        suggestions=suggestions,
    )
