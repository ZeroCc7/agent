"""Reference image style analyzer using DashScope Qwen-VL.

Analyzes a reference photo and returns the slider parameters + curve control
points that characterize its visual style. The output dict maps directly to
CurrentParams + CurveParams fields.
"""

import json
import os
import re
from pathlib import Path

import dashscope
from dashscope import MultiModalConversation

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_SYSTEM = (
    "你是一位有十年经验的专业摄影师和调色师，精通 Lightroom、Photoshop 等修图工具。"
    "你的任务是：分析一张参考图的视觉风格，将其转化为可复现该风格的具体参数值。"
    "这些参数将被应用到另一张照片上，目标是让那张照片呈现出与参考图相近的视觉氛围。"
    "你必须做到：参数值具体、精准，能真正体现参考图的色调特征，不说套话，不给无意义的中性默认值。"
)

_PROMPT = """\
仔细观察这张参考图，从以下维度进行量化分析：

【曝光与亮度】
- 整体曝光水平：偏亮（日系清透）、偏暗（电影感）还是正常曝光？
- 暗部处理：阴影是否被提亮（灰雾/胶片感），还是压暗（强对比/黑位下沉）？
- 高光处理：高光是否有压制（保留细节）或轻微溢出倾向？

【对比度】
- 整体对比强弱：高对比（明暗分明）、中等，还是低对比（柔和/平淡）？
- 是否存在局部拉伸（暗部/亮部分别处理）？

【色彩】
- 饱和度：鲜艳（高饱和）、自然，还是偏灰/褪色（低饱和）？
- 色温：偏暖（金黄/琥珀）还是偏冷（蓝调/青冷）？
- 色偏：是否有明显色偏（偏绿、偏品红、偏青等）？
- 颜色分离：高光和阴影是否有不同色彩倾向（如高光暖+阴影冷的电影分色）？

【锐度与质感】
- 画面是锐利清晰，还是柔和/胶片颗粒感的朦胧？

基于以上分析，输出下面的 JSON（只输出 JSON，不含任何其他文字）：

━━ 参数说明 ━━
  brightness    整体亮度，-60~60，0=原图，正=更亮，负=更暗
  contrast      对比度，-60~60，正=更强，负=更柔
  highlights    高光控制，-100~100，负=压制高光，正=拉亮高光
  shadows       阴影控制，-100~100，正=提亮暗部，负=压暗
  whites        白点，-100~100，控制极亮区域
  blacks        黑点，-100~100，控制极暗区域
  saturation    饱和度，-60~60，正=鲜艳，负=去色/褪色
  vibrance      自然饱和度，-60~60，优先提升低饱和区域，保护肤色
  clarity       清晰度，-60~60，正=通透质感，负=柔焦奶油感
  sharpness     锐度，-60~60，正=更锐，负=更柔
  color_temp    色温，-100~100，负=冷蓝，正=暖黄
  vignette      暗角，-100~100，负=边缘压暗（电影感），正=边缘提亮
  grain         颗粒感，0~100，模拟胶片颗粒
  shadow_tint           阴影色相，0~360
  shadow_tint_strength  阴影色调强度，0~100
  highlight_tint        高光色相，0~360
  highlight_tint_strength 高光色调强度，0~100
  smooth_skin   磨皮开关，true/false（参考图有人像且皮肤明显柔化时开启）
  smooth_level  磨皮程度，0~100
  brighten_skin 提亮肤色，true/false

━━ 色彩曲线（curve_params）━━
控制点格式：[输入值, 输出值]，范围 0-255（整数）
必须包含 [0,Y0] 和 [255,Y255] 两个端点，中间可加 1-4 个控制点
  rgb   主曲线，控制整体明暗与对比
  r     红色通道（增大=偏红/暖，减小=偏青）
  g     绿色通道（增大=偏绿，减小=偏品红）
  b     蓝色通道（增大=偏蓝/冷，减小=偏黄）

━━ 规则 ━━
1. 参数必须真实反映图片，不要给无意义的中性值（如全部填 0）
2. 曲线是风格的核心，必须认真分析并给出有差异的控制点
3. brightness/highlights/shadows 等滑块和曲线可以同时使用，共同实现效果
4. style_name 要简洁有识别度（2-5字），explanation 要说清"为什么这么调"（30-60字）
5. 若图片色彩风格不明显，曲线可用直线，但滑块仍需如实填写

输出格式：
{
  "brightness": 整数,
  "contrast": 整数,
  "highlights": 整数,
  "shadows": 整数,
  "whites": 整数,
  "blacks": 整数,
  "saturation": 整数,
  "vibrance": 整数,
  "clarity": 整数,
  "sharpness": 整数,
  "color_temp": 整数,
  "vignette": 整数,
  "grain": 整数,
  "shadow_tint": 整数,
  "shadow_tint_strength": 整数,
  "highlight_tint": 整数,
  "highlight_tint_strength": 整数,
  "smooth_skin": bool,
  "smooth_level": 整数,
  "brighten_skin": bool,
  "curve_params": {
    "rgb": [[整数,整数], ...],
    "r":   [[整数,整数], ...],
    "g":   [[整数,整数], ...],
    "b":   [[整数,整数], ...]
  },
  "style_name": "字符串",
  "explanation": "字符串"
}"""

_INT_FIELDS_CLAMP = {
    "brightness": (-60, 60),
    "contrast": (-60, 60),
    "highlights": (-100, 100),
    "shadows": (-100, 100),
    "whites": (-100, 100),
    "blacks": (-100, 100),
    "saturation": (-60, 60),
    "vibrance": (-60, 60),
    "clarity": (-60, 60),
    "sharpness": (-60, 60),
    "color_temp": (-100, 100),
    "vignette": (-100, 100),
    "grain": (0, 100),
    "shadow_tint": (0, 360),
    "shadow_tint_strength": (0, 100),
    "highlight_tint": (0, 360),
    "highlight_tint_strength": (0, 100),
    "smooth_level": (0, 100),
}

_IDENTITY_CURVE = [[0, 0], [255, 255]]
_IDENTITY_CURVES = {"rgb": _IDENTITY_CURVE, "r": _IDENTITY_CURVE, "g": _IDENTITY_CURVE, "b": _IDENTITY_CURVE}


def _file_uri(file_path: Path) -> str:
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"file://{abs_path}"


def _image_ref(file_path: Path) -> str:
    if os.getenv("USE_BASE64", "").lower() in ("1", "true"):
        from app.core.image_gen import _encode_file
        return _encode_file(file_path)
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
        return "\n".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("text")
        )
    return str(content)


def _parse_and_normalize(text: str) -> dict:
    """Parse model output and normalize to a valid parameter dict.

    Always returns a complete dict — falls back to neutral values on any
    parse failure so the caller never needs to handle a partial result.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    try:
        raw = json.loads(match.group() if match else cleaned)
    except (json.JSONDecodeError, AttributeError):
        return {
            **{k: 0 for k in _INT_FIELDS_CLAMP},
            "smooth_skin": False,
            "brighten_skin": False,
            "curve_params": _IDENTITY_CURVES,
            "style_name": "参考风格",
            "explanation": text[:200].strip(),
        }

    result: dict = {}

    for field, (lo, hi) in _INT_FIELDS_CLAMP.items():
        val = raw.get(field, 0)
        try:
            result[field] = max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            result[field] = 0

    result["smooth_skin"] = bool(raw.get("smooth_skin", False))
    result["brighten_skin"] = bool(raw.get("brighten_skin", False))

    raw_curves = raw.get("curve_params") or {}
    curves: dict = {}
    for ch in ("rgb", "r", "g", "b"):
        pts = raw_curves.get(ch) if isinstance(raw_curves, dict) else None
        if not isinstance(pts, list) or len(pts) < 2:
            curves[ch] = list(_IDENTITY_CURVE)
        else:
            try:
                curves[ch] = [
                    [max(0, min(255, int(p[0]))), max(0, min(255, int(p[1])))]
                    for p in pts if len(p) >= 2
                ]
                if len(curves[ch]) < 2:
                    curves[ch] = list(_IDENTITY_CURVE)
            except (TypeError, ValueError):
                curves[ch] = list(_IDENTITY_CURVE)
    result["curve_params"] = curves

    result["style_name"] = str(raw.get("style_name", "")).strip() or "参考风格"
    result["explanation"] = str(raw.get("explanation", "")).strip()

    return result


_COMPARE_SYSTEM = (
    "你是一位有十年经验的专业摄影师和调色师，精通 Lightroom、Photoshop 等修图工具。"
    "你的任务是：对比两张图片，找出当前效果图与目标参考图之间的风格差距，"
    "输出一套修正后的完整参数集，用于重新处理原始照片，使其更接近参考图的视觉风格。"
    "你必须做到：精准识别两图之间的具体差异，给出有针对性的修正值，不说套话。"
)

_COMPARE_PROMPT = """\
你收到两张图：
【图A · 当前效果图】：这是对原始照片应用了参考风格参数后的处理结果。
【图B · 目标参考图】：这是希望达到的目标风格。

请仔细比对两张图，找出图A与图B之间的风格差距，重点关注：
- 色温偏差（A偏冷/偏暖？与B相比）
- 对比度强弱（A的明暗关系与B是否匹配）
- 饱和度差异（A比B更鲜艳还是更灰）
- 高光/阴影细节（亮部暗部的处理方向是否对齐）
- 色调倾向（色偏、分色方向）
- 曲线形态（整体S型强度、色彩通道方向）

基于以上差距分析，输出一套修正后的完整参数集（用于重新处理原始照片）。
这套参数要在原有基础上进行修正，使结果更贴近图B。

━━ 参数说明 ━━
  brightness    整体亮度，-60~60，0=原图，正=更亮，负=更暗
  contrast      对比度，-60~60，正=更强，负=更柔
  highlights    高光控制，-100~100，负=压制高光，正=拉亮高光
  shadows       阴影控制，-100~100，正=提亮暗部，负=压暗
  whites        白点，-100~100，控制极亮区域
  blacks        黑点，-100~100，控制极暗区域
  saturation    饱和度，-60~60，正=鲜艳，负=去色/褪色
  vibrance      自然饱和度，-60~60，优先提升低饱和区域，保护肤色
  clarity       清晰度，-60~60，正=通透质感，负=柔焦奶油感
  sharpness     锐度，-60~60，正=更锐，负=更柔
  color_temp    色温，-100~100，负=冷蓝，正=暖黄
  vignette      暗角，-100~100，负=边缘压暗（电影感），正=边缘提亮
  grain         颗粒感，0~100，模拟胶片颗粒
  shadow_tint           阴影色相，0~360
  shadow_tint_strength  阴影色调强度，0~100
  highlight_tint        高光色相，0~360
  highlight_tint_strength 高光色调强度，0~100
  smooth_skin   磨皮开关，true/false
  smooth_level  磨皮程度，0~100
  brighten_skin 提亮肤色，true/false

━━ 色彩曲线（curve_params）━━
控制点格式：[输入值, 输出值]，范围 0-255（整数）
必须包含 [0,Y0] 和 [255,Y255] 两个端点，中间可加 1-4 个控制点
  rgb   主曲线，控制整体明暗与对比
  r     红色通道（增大=偏红/暖，减小=偏青）
  g     绿色通道（增大=偏绿，减小=偏品红）
  b     蓝色通道（增大=偏蓝/冷，减小=偏黄）

━━ 规则 ━━
1. 参数必须真实反映比对结果，不要给无意义的中性值
2. 曲线是风格核心，必须认真对比两图的色彩通道差异
3. style_name 沿用原风格名，explanation 重点说明与上次相比做了哪些修正、为什么（30-60字）

输出格式：
{
  "brightness": 整数,
  "contrast": 整数,
  "highlights": 整数,
  "shadows": 整数,
  "whites": 整数,
  "blacks": 整数,
  "saturation": 整数,
  "vibrance": 整数,
  "clarity": 整数,
  "sharpness": 整数,
  "color_temp": 整数,
  "vignette": 整数,
  "grain": 整数,
  "shadow_tint": 整数,
  "shadow_tint_strength": 整数,
  "highlight_tint": 整数,
  "highlight_tint_strength": 整数,
  "smooth_skin": bool,
  "smooth_level": 整数,
  "brighten_skin": bool,
  "curve_params": {
    "rgb": [[整数,整数], ...],
    "r":   [[整数,整数], ...],
    "g":   [[整数,整数], ...],
    "b":   [[整数,整数], ...]
  },
  "style_name": "字符串",
  "explanation": "字符串"
}"""


def compare_result(result_path: Path, reference_path: Path) -> dict:
    """Compare the current edit result against the reference image and return
    corrected parameters to apply to the original photo.

    Args:
        result_path: Path to the already-processed result image (outputs/).
        reference_path: Path to the reference/target image (uploads/).

    Returns:
        Same schema as analyze_reference.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未配置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")

    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": [{"text": _COMPARE_SYSTEM}]},
            {"role": "user", "content": [
                {"image": _image_ref(result_path)},
                {"image": _image_ref(reference_path)},
                {"text": _COMPARE_PROMPT},
            ]},
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"AI 比对失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("模型返回内容为空")

    return _parse_and_normalize(text)


def analyze_reference(image_path: Path) -> dict:
    """Analyze a reference image and return its style as a parameter dict.

    Returns:
        dict with all CurrentParams fields + curve_params + style_name + explanation.
    Raises:
        ValueError: DASHSCOPE_API_KEY not set.
        RuntimeError: API call failed or empty response.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未配置 DASHSCOPE_API_KEY")

    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")

    rsp = MultiModalConversation.call(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": [{"text": _SYSTEM}]},
            {"role": "user", "content": [
                {"image": _image_ref(Path(image_path))},
                {"text": _PROMPT},
            ]},
        ],
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"参考图分析失败 [{rsp.code}]: {rsp.message}")

    text = _extract_text(rsp)
    if not text:
        raise RuntimeError("模型返回内容为空")

    return _parse_and_normalize(text)
