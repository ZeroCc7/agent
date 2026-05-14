"""DashScope wan2.7-image photo editing integration.

Flow: uploaded image + user instruction → wan2.7-image → edited PIL Image

Image URL resolution (in priority order):
  1. PUBLIC_BASE_URL env var  → {PUBLIC_BASE_URL}/uploads/{filename}
  2. Local file:// URI        → works when DashScope SDK processes on same host
"""

import io
import os
import urllib.request
from pathlib import Path

import dashscope
from dashscope.aigc.image_generation import ImageGeneration
from dashscope.api_entities.dashscope_response import Message
from PIL import Image

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

# Prepended to every instruction to steer toward subtle, natural results
_STYLE_GUIDE = (
    "这是一张日常生活照片，请按照以下要求对图片进行美化处理，"
    "保持照片自然真实，不要过度修图："
)

# Aspect-ratio → wan2.7-image size string mapping
_SIZE_MAP = [
    (1.6, "1280*720"),   # wide landscape
    (0.9, "1024*1024"),  # near-square
    (0.0, "720*1280"),   # portrait
]


def _pick_size(img: Image.Image) -> str:
    ratio = img.width / img.height
    for threshold, size in _SIZE_MAP:
        if ratio > threshold:
            return size
    return "1024*1024"


def _image_url(file_path: Path) -> str:
    """Return an accessible image URL for DashScope."""
    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if public_base:
        return f"{public_base}/uploads/{file_path.name}"
    # file:// works for local single-machine deployments
    return file_path.resolve().as_uri()


def edit_image(image_path: Path, instruction: str) -> Image.Image:
    """
    Edit a photo using DashScope wan2.7-image (multimodal img2img).

    Args:
        image_path: Absolute or relative path to the source image (under uploads/).
        instruction: User's natural-language instruction in Chinese.

    Returns:
        Edited PIL Image.

    Raises:
        ValueError: DASHSCOPE_API_KEY not configured.
        RuntimeError: DashScope API call failed (includes actionable hint).
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

    url = _image_url(file_path)
    prompt = f"{_STYLE_GUIDE}{instruction}"

    message = Message(
        role="user",
        content=[
            {"image": url},
            {"text": prompt},
        ],
    )

    rsp = ImageGeneration.call(
        model="wan2.7-image",
        api_key=api_key,
        messages=[message],
        n=1,
        size=size,
    )

    if rsp.status_code != 200:
        hint = ""
        msg_lower = str(getattr(rsp, "message", "")).lower()
        if any(k in msg_lower for k in ("image", "url", "access", "download")):
            hint = (
                "\n\n提示：DashScope 无法访问图片。"
                "请在 .env 中设置 PUBLIC_BASE_URL=https://你的公网域名"
            )
        raise RuntimeError(
            f"DashScope 调用失败 [{rsp.code}]: {rsp.message}{hint}"
        )

    result_url = rsp.output.results[0].url

    with urllib.request.urlopen(result_url, timeout=120) as resp:
        data = resp.read()

    return Image.open(io.BytesIO(data)).copy()
