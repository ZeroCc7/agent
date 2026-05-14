"""DashScope wan2.7-image-pro photo editing.

Image input priority:
  1. file:// URI  — local dev, same machine as the FastAPI server
  2. base64       — fallback, or set USE_BASE64=true in .env
"""

import base64
import io
import mimetypes
import os
import urllib.request
from pathlib import Path

import dashscope
from dashscope.aigc.image_generation import ImageGeneration
from dashscope.api_entities.dashscope_response import Message
from PIL import Image

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_STYLE_GUIDE = (
    "这是一张需要美化的日常生活照片，请按照以下要求处理，"
    "保持照片自然真实，不要过度修图："
)


def _encode_file(file_path: Path) -> str:
    """Return base64 data URI for the image file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def _file_uri(file_path: Path) -> str:
    """file://E:/path/to/img.jpg — matches DashScope's expected format."""
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"file://{abs_path}"


def _image_ref(file_path: Path) -> str:
    """Return the image reference string to pass in message content."""
    if os.getenv("USE_BASE64", "").lower() in ("1", "true"):
        return _encode_file(file_path)
    return _file_uri(file_path)


def _pick_size(img: Image.Image) -> str:
    ratio = img.width / img.height
    if ratio > 1.5:
        return "2K"   # landscape → 2560×1440
    elif ratio < 0.67:
        return "1440*2560"  # portrait
    else:
        return "1440*1440"  # near-square


def edit_image(image_path: Path, instruction: str) -> Image.Image:
    """
    Edit a photo using DashScope wan2.7-image-pro.

    Args:
        image_path: Path to uploaded image (under uploads/).
        instruction: User's Chinese natural-language instruction.

    Returns:
        Edited PIL Image.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError(
            "未配置 DASHSCOPE_API_KEY，请在 .env 文件中添加：\n"
            "DASHSCOPE_API_KEY=your_key_here"
        )

    file_path = Path(image_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    with Image.open(file_path) as img:
        size = _pick_size(img)

    image_ref = _image_ref(file_path)
    prompt = f"{_STYLE_GUIDE}{instruction}"

    message = Message(
        role="user",
        content=[
            {"text": prompt},
            {"image": image_ref},
        ],
    )

    rsp = ImageGeneration.call(
        model="wan2.7-image-pro",
        api_key=api_key,
        messages=[message],
        watermark=False,
        n=1,
        size=size,
    )

    if rsp.status_code != 200:
        raise RuntimeError(
            f"DashScope 调用失败 [{rsp.code}]: {rsp.message}\n"
            "若提示图片无法访问，请在 .env 中设置 USE_BASE64=true"
        )

    # Parse response: rsp.output.choices[i]["message"]["content"][j]
    for choice in rsp.output.choices:
        for item in choice["message"]["content"]:
            if item.get("type") == "image":
                result_url = item["image"]
                with urllib.request.urlopen(result_url, timeout=120) as resp:
                    data = resp.read()
                return Image.open(io.BytesIO(data)).copy()

    raise RuntimeError("DashScope 响应中未找到图片结果")
