import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from app.core.background import apply_background
from app.core.curve_processor import apply_curves
from app.core.image_analyzer import analyze_photo
from app.core.image_gen import edit_image
from app.core.image_processor import apply_basic_edits, apply_extended_edits
from app.core.param_advisor import suggest_params
from app.core.portrait import apply_portrait
from app.core.prompt_store import (
    create_prompt, delete_prompt, get_categories,
    list_prompts, update_prompt,
)
from app.core.preset_store import (
    create_preset as _create_preset,
    delete_preset as _delete_preset,
    get_categories as _get_preset_categories,
    list_presets,
    update_preset as _update_preset,
)
from app.core.reference_analyzer import analyze_reference, compare_result
from app.types.models import (
    AIEditRequest, AnalyzeRequest, AnalyzeResponse,
    CurrentParams, CurveParams, EditResponse,
    ExtendedEditParams,
    CompareStyleRequest, CompareStyleResponse,
    ManualEditRequest, Preset, PresetCreate, PresetUpdate,
    Prompt, PromptCreate, PromptUpdate,
    ReferenceAnalyzeRequest, ReferenceAnalyzeResponse,
    StyleSuggestion, SuggestRequest, SuggestResponse,
)

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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        raw = await asyncio.to_thread(analyze_photo, src)
        suggestions = [StyleSuggestion(**item) for item in raw]
        return AnalyzeResponse(suggestions=suggestions)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"照片分析失败：{e}")


@router.post("/edit/manual", response_model=EditResponse)
async def manual_edit(request: ManualEditRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        with Image.open(src) as img:
            result = img.convert("RGB")
            result = apply_basic_edits(result, request.edit_params)
            result = apply_extended_edits(result, request.extended_params)
            result = apply_portrait(result, request.portrait_params)
            result = apply_background(result, request.background_params)
            result = apply_curves(result, request.curve_params)

            out_name = f"edited_{uuid.uuid4().hex[:10]}.jpg"
            out_path = OUTPUT_DIR / out_name

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
        img = Image.open(src).convert("RGB")
        ref_img = None
        if request.reference_filename:
            ref_path = UPLOAD_DIR / request.reference_filename
            if ref_path.exists():
                ref_img = Image.open(ref_path).convert("RGB")
        result = await asyncio.to_thread(edit_image, img, request.instruction, ref_img)

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


@router.post("/edit/suggest", response_model=SuggestResponse)
async def suggest(request: SuggestRequest):
    if not request.instruction.strip():
        raise HTTPException(400, "请输入描述")

    try:
        current_dict = dict(request.current_params)
        raw = await asyncio.to_thread(suggest_params, request.instruction, current_dict)

        # Merge LLM output back into CurrentParams (ignore unknown keys)
        merged = {**current_dict, **{k: v for k, v in raw.items() if k in current_dict}}
        explanation = raw.get("explanation", "")

        # Parse optional curve_params from LLM output
        curve_params = None
        raw_curves = raw.get("curve_params")
        if isinstance(raw_curves, dict):
            try:
                curve_params = CurveParams(**raw_curves)
            except Exception:
                curve_params = None

        return SuggestResponse(
            params=CurrentParams(**merged),
            explanation=explanation,
            curve_params=curve_params,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"参数建议失败：{e}")


# ── Prompt library ────────────────────────────────────────────────────

@router.get("/prompts")
async def prompts_list(search: str = "", category: str = ""):
    return {
        "prompts": list_prompts(search, category),
        "categories": get_categories(),
    }


@router.post("/prompts", response_model=Prompt)
async def prompts_create(data: PromptCreate):
    if not data.name.strip():
        raise HTTPException(400, "名称不能为空")
    if not data.prompt.strip():
        raise HTTPException(400, "提示词内容不能为空")
    return create_prompt(data.name, data.prompt, data.category, data.tags)


@router.put("/prompts/{prompt_id}", response_model=Prompt)
async def prompts_update(prompt_id: str, data: PromptUpdate):
    item = update_prompt(
        prompt_id,
        name=data.name,
        prompt=data.prompt,
        category=data.category,
        tags=data.tags,
    )
    if item is None:
        raise HTTPException(404, "提示词不存在")
    return item


@router.delete("/prompts/{prompt_id}")
async def prompts_delete(prompt_id: str):
    if not delete_prompt(prompt_id):
        raise HTTPException(404, "提示词不存在")
    return {"ok": True}


# ── Reference image analysis ──────────────────────────────────────────

@router.post("/analyze-reference", response_model=ReferenceAnalyzeResponse)
async def analyze_reference_image(request: ReferenceAnalyzeRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")

    try:
        raw = await asyncio.to_thread(analyze_reference, src)

        params_dict = {k: v for k, v in raw.items()
                       if k not in ("curve_params", "style_name", "explanation")}
        curve_dict = raw.get("curve_params") or {}

        return ReferenceAnalyzeResponse(
            params=CurrentParams(**params_dict),
            curve_params=CurveParams(**curve_dict),
            style_name=raw.get("style_name", "参考风格"),
            explanation=raw.get("explanation", ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"参考图分析失败：{e}")


@router.post("/compare-style", response_model=CompareStyleResponse)
async def compare_style(request: CompareStyleRequest):
    result_path = OUTPUT_DIR / request.result_filename
    reference_path = UPLOAD_DIR / request.reference_filename

    if not result_path.exists():
        raise HTTPException(404, "效果图不存在，请先应用参数生成效果图")
    if not reference_path.exists():
        raise HTTPException(404, "参考图不存在，请重新上传")

    try:
        raw = await asyncio.to_thread(compare_result, result_path, reference_path)

        params_dict = {k: v for k, v in raw.items()
                       if k not in ("curve_params", "style_name", "explanation")}
        curve_dict = raw.get("curve_params") or {}

        return CompareStyleResponse(
            params=CurrentParams(**params_dict),
            curve_params=CurveParams(**curve_dict),
            explanation=raw.get("explanation", ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI 比对失败：{e}")


# ── Parameter preset library ──────────────────────────────────────────

@router.get("/presets")
async def presets_list(search: str = "", category: str = ""):
    return {
        "presets": list_presets(search, category),
        "categories": _get_preset_categories(),
    }


@router.post("/presets", response_model=Preset)
async def presets_create(data: PresetCreate):
    if not data.name.strip():
        raise HTTPException(400, "名称不能为空")
    return _create_preset(
        data.name,
        data.params.model_dump(),
        data.curve_params.model_dump(),
        data.category,
        data.tags,
    )


@router.put("/presets/{preset_id}", response_model=Preset)
async def presets_update(preset_id: str, data: PresetUpdate):
    item = _update_preset(
        preset_id,
        name=data.name,
        params=data.params.model_dump() if data.params else None,
        curve_params=data.curve_params.model_dump() if data.curve_params else None,
        category=data.category,
        tags=data.tags,
    )
    if item is None:
        raise HTTPException(404, "预设不存在")
    return item


@router.delete("/presets/{preset_id}")
async def presets_delete(preset_id: str):
    if not _delete_preset(preset_id):
        raise HTTPException(404, "预设不存在")
    return {"ok": True}
