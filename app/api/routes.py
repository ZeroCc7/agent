import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from app.core.background import apply_background
from app.core.image_gen import edit_image
from app.core.image_processor import apply_basic_edits
from app.core.portrait import apply_portrait
from app.types.models import AIEditRequest, EditResponse, ManualEditRequest

router = APIRouter()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "文件必须是图片格式")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"不支持的格式，请使用 JPG/PNG/WebP")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "文件过大（最大 50MB）")

    filename = f"{uuid.uuid4()}{suffix}"
    path = UPLOAD_DIR / filename
    path.write_bytes(content)

    with Image.open(path) as img:
        width, height = img.size

    return {"filename": filename, "width": width, "height": height}


@router.post("/edit/manual", response_model=EditResponse)
async def manual_edit(request: ManualEditRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        with Image.open(src) as img:
            result = img.convert("RGB")
            result = apply_basic_edits(result, request.edit_params)
            result = apply_portrait(result, request.portrait_params)
            result = apply_background(result, request.background_params)

            out_name = f"edited_{uuid.uuid4().hex[:10]}.jpg"
            out_path = OUTPUT_DIR / out_name

            # Preserve RGBA for background-removed images
            if result.mode == "RGBA":
                out_name = out_name.replace(".jpg", ".png")
                out_path = OUTPUT_DIR / out_name
                result.save(out_path, "PNG")
            else:
                result.save(out_path, "JPEG", quality=92, optimize=True)

        return EditResponse(success=True, result_filename=out_name)
    except Exception as e:
        raise HTTPException(500, f"处理失败：{e}")


@router.post("/edit/ai", response_model=EditResponse)
async def ai_edit(request: AIEditRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    if not request.instruction.strip():
        raise HTTPException(400, "请描述你想要的效果")

    try:
        # DashScope call is blocking — offload to thread pool
        result = await asyncio.to_thread(edit_image, src, request.instruction)

        out_name = f"ai_{uuid.uuid4().hex[:10]}"
        if result.mode == "RGBA":
            out_name += ".png"
            result.save(OUTPUT_DIR / out_name, "PNG")
        else:
            out_name += ".jpg"
            result.convert("RGB").save(
                OUTPUT_DIR / out_name, "JPEG", quality=92, optimize=True
            )

        return EditResponse(success=True, result_filename=out_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI 生图失败：{e}")
