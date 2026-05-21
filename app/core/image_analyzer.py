"""Photo analysis using DashScope Qwen-VL.

Analyzes an uploaded photo and returns editing suggestions.
The model is given full freedom to assess the specific image;
we parse its output as JSON with a robust text fallback.
"""

import json
import os
import re
from pathlib import Path
from typing import List

import dashscope
from dashscope import MultiModalConversation

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_SYSTEM = (
    "你是一位有十年经验的专业摄影师和修图师，"
    "擅长分析日常生活照片并给出精准、有针对性的修图建议。"
    "你的建议必须结合这张照片的实际情况，指出具体问题，给出具体解决方案，不说套话。"
)

_PROMPT = """\
仔细观察这张照片：光线质量、色彩倾向、曝光、对比度、色温、构图、主体情况、整体氛围。

基于你对这张照片的实际判断，给出 4 种不同方向的修图方案，方案之间要有明显差异。
每种方案包含：
- style: 风格名（2-5字）
- description: 针对这张照片，这种修图会改变哪些具体视觉特征（30-80字）
- prompt: 直接给图像生成模型执行的详细修图指令，要描述具体的调整内容和预期效果

以 JSON 数组输出，不要任何代码块标记和多余文字：
[{"style":"...","description":"...","prompt":"..."},...]"""


def _file_uri(file_path: Path) -> str:
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"file://{abs_path}"


def _image_ref(file_path: Path) -> str:
    if os.getenv("USE_BASE64", "").lower() in ("1", "true"):
        import base64, mimetypes
        mime, _ = mimetypes.guess_type(str(file_path))
        if not mime or not mime.startswith("image/"):
            mime = "image/jpeg"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"
    return _file_uri(file_path)


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
        texts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text") or (item.get("type") == "text" and item.get("text", ""))
                if t:
                    texts.append(t)
        return "\n".join(texts)
    return str(content)


def _parse_json(text: str) -> List[dict]:
    """Try several patterns to extract a JSON array from model output."""
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    # Greedy match for outermost array
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try the whole cleaned string
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return []


def _text_to_suggestions(text: str) -> List[dict]:
    """
    Fallback: model returned plain text instead of JSON.
    Split on numbered or bolded sections and build suggestion cards.
    """
    suggestions = []

    # Pattern: "1. 风格名" / "**风格名**" / "### 风格名"
    sections = re.split(
        r"(?:^|\n)(?:\d+[\.\、]|\#{1,3}|\*{1,2})\s*(.{2,12}?)(?:\*{1,2})?\s*[\n：:]",
        text
    )

    for i in range(1, len(sections) - 1, 2):
        style = sections[i].strip()
        body  = sections[i + 1].strip() if i + 1 < len(sections) else ""
        if not style or not body:
            continue
        # First sentence as description, rest as prompt
        first_stop = re.search(r"[。！？\.!?]", body)
        if first_stop:
            desc   = body[:first_stop.end()].strip()
            prompt = body[first_stop.end():].strip() or desc
        else:
            desc   = body[:80].strip()
            prompt = body.strip()
        suggestions.append({"style": style, "description": desc, "prompt": prompt})
        if len(suggestions) == 4:
            break

    # Last resort: wrap the entire response as one suggestion
    if not suggestions:
        suggestions.append({
            "style": "AI 建议",
            "description": text[:120].strip(),
            "prompt": text.strip(),
        })

    return suggestions


def analyze_photo(image_path: Path) -> List[dict]:
    """
    Analyze a photo and return editing style suggestions.

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
        messages=[
            {
                "role": "system",
                "content": [{"text": _SYSTEM}],
            },
            {
                "role": "user",
                "content": [
                    {"image": _image_ref(Path(image_path))},
                    {"text": _PROMPT},
                ],
            },
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"照片分析失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("模型返回内容为空")

    raw = _parse_json(text)

    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        style = str(item.get("style", "")).strip()
        desc  = str(item.get("description", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if style and (desc or prompt):
            result.append({
                "style":       style,
                "description": desc or prompt[:80],
                "prompt":      prompt or desc,
            })

    if not result:
        result = _text_to_suggestions(text)

    return result[:6]  # cap at 6 cards max
