"""Photo analysis using DashScope Qwen-VL.

Analyzes an uploaded photo and returns 4 style/editing suggestions,
each with a ready-to-use prompt for wan2.7-image-pro.
"""

import json
import os
import re
from pathlib import Path
from typing import List

import dashscope
from dashscope import MultiModalConversation

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_PROMPT = """仔细分析这张日常生活照片的内容、光线质量、色彩和整体氛围。

请生成 4 种适合这张照片的修图风格建议，要求：
1. 4 种风格之间有明显差异（例如：清新自然 / 胶片复古 / 日系小清新 / 电影感浓郁）
2. 每种风格都要适合日常生活照，效果自然不夸张
3. prompt 字段要具体，可直接发给图像生成模型使用

只返回如下 JSON 数组，不要包含任何其他内容：
[
  {
    "style": "风格名（2-4字）",
    "description": "一句话说明这种风格的视觉特点",
    "prompt": "详细修图指令，描述需要调整哪些具体内容"
  }
]"""


def _file_uri(file_path: Path) -> str:
    """file://E:/path/to/img.jpg  — matches DashScope's expected format."""
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"file://{abs_path}"


def _image_ref(file_path: Path) -> str:
    if os.getenv("USE_BASE64", "").lower() in ("1", "true"):
        from app.core.image_gen import _encode_file
        return _encode_file(file_path)
    return _file_uri(file_path)


def _extract_text(rsp) -> str:
    """Pull the assistant's text from a MultiModalConversation response."""
    choices = rsp.output.choices
    if not choices:
        return ""
    choice = choices[0]

    # DashScope SDK may return dicts or objects depending on version
    try:
        content = choice["message"]["content"]
    except TypeError:
        content = choice.message.content

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                # type=="text" or just a "text" key
                if item.get("type") == "text":
                    return item.get("text", "")
                if "text" in item:
                    return item["text"]
    return str(content)


def _parse_json(text: str) -> List[dict]:
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(match.group() if match else text)


def analyze_photo(image_path: Path) -> List[dict]:
    """
    Analyze a photo with Qwen-VL and return editing style suggestions.

    Returns:
        List of dicts: [{style, description, prompt}, ...]
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未配置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")

    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[{
            "role": "user",
            "content": [
                {"image": _image_ref(Path(image_path))},
                {"text": _PROMPT},
            ],
        }],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"照片分析失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("模型返回内容为空")

    suggestions = _parse_json(text)

    # Validate and normalise
    result = []
    for item in suggestions:
        if isinstance(item, dict) and all(k in item for k in ("style", "description", "prompt")):
            result.append({
                "style": str(item["style"])[:20],
                "description": str(item["description"])[:80],
                "prompt": str(item["prompt"]),
            })
    if not result:
        raise RuntimeError("无法解析模型返回的风格建议")
    return result
