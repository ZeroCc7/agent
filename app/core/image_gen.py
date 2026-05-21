"""DashScope wan2.7-image-pro image-to-image editing with optional style reference."""

import base64
import io
import os
import urllib.request
from typing import Optional

import dashscope
from dashscope import MultiModalConversation
from dashscope.aigc.image_generation import ImageGeneration
from dashscope.api_entities.dashscope_response import Message
from PIL import Image

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_STYLE_GUIDE = (
    "这是一张需要美化的日常生活照片，请按照以下要求处理，"
    "保持照片自然真实，不要过度修图："
)


def _encode_image(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _pick_size(img: Image.Image) -> str:
    ratio = img.width / img.height
    if ratio > 1.5:
        return "1280*720"
    elif ratio < 0.67:
        return "720*1280"
    return "1024*1024"


def _describe_reference_style(ref_img: Image.Image, api_key: str) -> str:
    model = os.getenv("ANALYZE_MODEL", "qwen3.6-plus")
    buf = io.BytesIO()
    thumb = ref_img.convert("RGB")
    thumb.thumbnail((512, 512), Image.LANCZOS)
    thumb.save(buf, "JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    try:
        rsp = MultiModalConversation.call(
            model=model,
            api_key=api_key,
            messages=[{
                "role": "user",
                "content": [
                    {"image": f"data:image/jpeg;base64,{b64}"},
                    {"text": (
                        "用不超过20字描述这张图片的色调和风格，"
                        "例如：暖色调、低对比度、胶片质感。"
                        "只输出风格描述，不要其他内容。"
                    )},
                ],
            }],
        )
        if rsp.status_code != 200:
            return ""
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
            ).strip()
        return str(content).strip()
    except Exception:
        return ""


def edit_image(
    img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
) -> Image.Image:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError(
            "未配置 DASHSCOPE_API_KEY，请在 .env 文件中添加：\n"
            "DASHSCOPE_API_KEY=your_key_here"
        )

    size = _pick_size(img)
    src_b64 = _encode_image(img)

    if reference_img is not None:
        style_desc = _describe_reference_style(reference_img, api_key)
        ref_b64 = _encode_image(reference_img)
        style_hint = f"（{style_desc}）" if style_desc else ""
        text = (
            f"图1是原图，图2是风格参考。"
            f"{_STYLE_GUIDE}{instruction}，"
            f"参考图2的色调和风格{style_hint}"
        )
        content = [
            {"text": text},
            {"image": src_b64},
            {"image": ref_b64},
        ]
    else:
        content = [
            {"text": f"{_STYLE_GUIDE}{instruction}"},
            {"image": src_b64},
        ]

    message = Message(role="user", content=content)
    rsp = ImageGeneration.call(
        model="wan2.7-image-pro",
        api_key=api_key,
        messages=[message],
        watermark=False,
        n=1,
        size=size,
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"DashScope 调用失败 [{rsp.code}]: {rsp.message}")

    for choice in rsp.output.choices:
        for item in choice["message"]["content"]:
            if item.get("type") == "image":
                with urllib.request.urlopen(item["image"], timeout=120) as resp:
                    data = resp.read()
                return Image.open(io.BytesIO(data)).copy()

    raise RuntimeError("DashScope 响应中未找到图片结果")
