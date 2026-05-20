import base64
import io
import json
import os
from typing import Optional

import dashscope
from dashscope import MultiModalConversation
from PIL import Image

from app.types.models import ReviewScore

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

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


def _img_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


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


def run_review_agent(
    original_img: Image.Image,
    edited_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
    round_num: int = 1,
) -> ReviewScore:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")

    user_content = [
        {"image": _img_data_uri(original_img)},
        {"text": "原始图片"},
        {"image": _img_data_uri(edited_img)},
        {"text": f"第{round_num}轮修图结果"},
    ]

    if reference_img is not None:
        user_content += [
            {"image": _img_data_uri(reference_img)},
            {"text": "参考图片（目标风格）"},
        ]

    user_content.append({"text": f"用户指令：{instruction}\n\n请评分并给出改进建议。"})

    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": [{"text": _SYSTEM}]},
            {"role": "user", "content": user_content},
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"ReviewAgent 调用失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("ReviewAgent 返回内容为空")

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
