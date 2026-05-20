import base64
import io
import json
import os
from typing import Optional

import dashscope
from dashscope import MultiModalConversation
from PIL import Image

from app.types.models import (
    AgentEditOutput, BackgroundParams, CurveParams,
    EditParams, ExtendedEditParams, PortraitParams, ReviewScore,
)

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

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

Adjust ONLY the parameters flagged as problematic. Do not change parameters that scored >= 8.

Return ONLY a valid JSON object with the same structure as below:
{
  "edit_params": {
    "brightness": <float 0.5-2.0>,
    "contrast": <float 0.5-2.0>,
    "saturation": <float 0.5-2.0>,
    "sharpness": <float 0.5-2.0>,
    "color_temp": <int -100 to 100>
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
  "explanation": "<one sentence in Chinese explaining the key adjustment>"
}

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
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")
    is_first = previous_output is None

    user_content = [
        {"image": _img_data_uri(original_img)},
        {"text": "原始图片"},
    ]

    if reference_img is not None:
        user_content += [
            {"image": _img_data_uri(reference_img)},
            {"text": "参考图片（请让效果尽量接近此风格）"},
        ]

    if is_first:
        user_text = f"用户指令：{instruction}"
    else:
        sugg_lines = "\n".join(
            f"  - {k}: {v}"
            for k, v in (review_score.suggestions if review_score else {}).items()
        )
        user_text = (
            f"用户指令：{instruction}\n\n"
            f"上一轮参数：\n{previous_output.model_dump_json(indent=2)}\n\n"
            f"审查反馈（请针对以下问题调整，不要大幅改动已合格的维度）：\n{sugg_lines}"
        )

    user_content.append({"text": user_text})

    system_prompt = _SYSTEM_FIRST if is_first else _SYSTEM_FEEDBACK
    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": [{"text": system_prompt}]},
            {"role": "user", "content": user_content},
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"EditingAgent 调用失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("EditingAgent 返回内容为空")

    return _parse(text)
