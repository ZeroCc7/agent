import asyncio
import base64
import io
import json
from typing import AsyncIterator, Optional

from PIL import Image

from app.core.background import apply_background
from app.core.color_transfer import color_transfer
from app.core.curve_processor import apply_curves
from app.core.editing_agent import run_editing_agent
from app.core.image_gen import edit_image as wan_edit_image
from app.core.image_processor import apply_basic_edits, apply_extended_edits
from app.core.portrait import apply_portrait
from app.core.review_agent import run_review_agent
from app.core.session_store import SessionStore
from app.types.models import AgentEditOutput, AgentIteration, ReviewScore

MAX_ROUNDS = 5
_store = SessionStore()


def _apply_params(original: Image.Image, params: AgentEditOutput) -> Image.Image:
    result = original.convert("RGB")
    result = apply_basic_edits(result, params.edit_params)
    result = apply_extended_edits(result, params.extended_params)
    result = apply_portrait(result, params.portrait_params)
    result = apply_background(result, params.background_params)
    result = apply_curves(result, params.curve_params)
    return result


def _to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_agent_loop(
    original_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
) -> AsyncIterator[str]:
    session_id = _store.create_session(instruction, has_reference=reference_img is not None)
    _store.save_original(session_id, original_img)
    if reference_img is not None:
        _store.save_reference(session_id, reference_img)

    # ── Color transfer pre-processing ────────────────────────────────
    # When a reference image is provided, apply LAB-space color transfer to
    # give the Agent a baseline that already matches the reference palette.
    # The Agent then only needs to make perceptual fine-tuning adjustments
    # rather than reconstructing the full color grade from scratch.
    base_img = original_img
    if reference_img is not None:
        yield _sse({"type": "progress", "round": 0, "status": "color_transfer", "session_id": session_id})
        try:
            base_img = await asyncio.to_thread(color_transfer, original_img, reference_img)
        except Exception as exc:
            yield _sse({"type": "progress", "round": 0, "status": "color_transfer_warn",
                        "message": f"颜色迁移跳过：{exc}", "session_id": session_id})

    session = _store.load_session(session_id)
    previous_output: Optional[AgentEditOutput] = None
    previous_review: Optional[ReviewScore] = None
    previous_edited_img: Optional[Image.Image] = None
    best_round = 0
    best_score = -1.0
    best_image: Optional[Image.Image] = None

    for round_num in range(1, MAX_ROUNDS + 1):
        yield _sse({"type": "progress", "round": round_num, "status": "editing", "session_id": session_id})

        try:
            edit_output = await asyncio.to_thread(
                run_editing_agent, base_img, instruction, reference_img,
                previous_output, previous_review, previous_edited_img,
            )
            # Apply those params on top of the CT baseline
            edited_img = await asyncio.to_thread(_apply_params, base_img, edit_output)

            yield _sse({"type": "progress", "round": round_num, "status": "reviewing", "session_id": session_id})

            review = await asyncio.to_thread(
                run_review_agent, original_img, edited_img, instruction, reference_img, round_num,
            )
        except Exception as exc:
            yield _sse({
                "type": "error",
                "round": round_num,
                "message": f"第 {round_num} 轮处理失败：{exc}",
            })
            # 若已有历史轮次，返回目前最佳结果；否则终止
            if best_image is not None:
                best_filename = session.iterations[best_round - 1].image_filename
                yield _sse({
                    "type": "done",
                    "session_id": session_id,
                    "best_round": best_round,
                    "final_score": round(best_score, 2),
                    "image_b64": _to_b64(best_image),
                    "image_url": f"/sessions/{session_id}/{best_filename}",
                })
            return

        overall = review.overall
        img_filename = _store.save_iteration_image(session_id, round_num, overall, edited_img)

        iteration = AgentIteration(
            round=round_num,
            image_filename=img_filename,
            params=edit_output,
            scores={
                "visual_quality": review.visual_quality,
                "instruction_match": review.instruction_match,
                "reference_match": review.reference_match,
                "overall": overall,
            },
            suggestions=review.suggestions,
            is_satisfied=review.is_satisfied,
        )
        session.iterations.append(iteration)

        if overall > best_score:
            best_score = overall
            best_round = round_num
            best_image = edited_img

        session.best_round = best_round
        _store.save_session(session)

        yield _sse({
            "type": "progress",
            "round": round_num,
            "status": "done_round",
            "score": round(overall, 2),
            "is_satisfied": review.is_satisfied,
            "session_id": session_id,
            "image_url": f"/sessions/{session_id}/{img_filename}",
            "explanation": edit_output.explanation,
            "suggestions": review.suggestions,
        })

        previous_output = edit_output
        previous_review = review
        previous_edited_img = edited_img

        if review.is_satisfied:
            break

    if best_image is None:
        yield _sse({"type": "error", "round": 0, "message": "所有轮次均失败，无法生成结果"})
        return

    best_filename = session.iterations[best_round - 1].image_filename
    yield _sse({
        "type": "done",
        "session_id": session_id,
        "best_round": best_round,
        "final_score": round(best_score, 2),
        "image_b64": _to_b64(best_image),
        "image_url": f"/sessions/{session_id}/{best_filename}",
    })


async def continue_agent_loop(
    session_id: str,
    extra_rounds: int,
) -> AsyncIterator[str]:
    """Continue editing from the session's current best image for extra_rounds more rounds."""
    session = _store.load_session(session_id)
    best_img = await asyncio.to_thread(_store.load_best_image, session_id)
    original_img = await asyncio.to_thread(_store.load_original_image, session_id)
    reference_img: Optional[Image.Image] = None
    if session.has_reference:
        reference_img = await asyncio.to_thread(_store.load_reference_image, session_id)

    start_round = len(session.iterations) + 1
    best_round = session.best_round
    best_score = (
        session.iterations[session.best_round - 1].scores["overall"]
        if session.best_round > 0 else -1.0
    )
    best_image = best_img

    previous_output: Optional[AgentEditOutput] = None
    previous_review: Optional[ReviewScore] = None
    previous_edited_img: Optional[Image.Image] = None

    for i in range(extra_rounds):
        round_num = start_round + i
        yield _sse({"type": "progress", "round": round_num, "status": "editing", "session_id": session_id})

        try:
            edit_output = await asyncio.to_thread(
                run_editing_agent, best_img, session.instruction, reference_img,
                previous_output, previous_review, previous_edited_img,
            )
            edited_img = await asyncio.to_thread(_apply_params, best_img, edit_output)
            yield _sse({"type": "progress", "round": round_num, "status": "reviewing", "session_id": session_id})
            review = await asyncio.to_thread(
                run_review_agent, original_img, edited_img, session.instruction, reference_img, round_num,
            )
        except Exception as exc:
            yield _sse({
                "type": "error",
                "round": round_num,
                "message": f"第 {round_num} 轮处理失败：{exc}",
            })
            break

        overall = review.overall
        img_filename = _store.save_iteration_image(session_id, round_num, overall, edited_img)

        iteration = AgentIteration(
            round=round_num,
            image_filename=img_filename,
            params=edit_output,
            scores={
                "visual_quality": review.visual_quality,
                "instruction_match": review.instruction_match,
                "reference_match": review.reference_match,
                "overall": overall,
            },
            suggestions=review.suggestions,
            is_satisfied=review.is_satisfied,
        )
        session.iterations.append(iteration)

        if overall > best_score:
            best_score = overall
            best_round = round_num
            best_image = edited_img

        session.best_round = best_round
        _store.save_session(session)

        yield _sse({
            "type": "progress",
            "round": round_num,
            "status": "done_round",
            "score": round(overall, 2),
            "is_satisfied": review.is_satisfied,
            "session_id": session_id,
            "image_url": f"/sessions/{session_id}/{img_filename}",
            "explanation": edit_output.explanation,
            "suggestions": review.suggestions,
        })

        previous_output = edit_output
        previous_review = review
        previous_edited_img = edited_img

        if review.is_satisfied:
            break

    best_filename = session.iterations[best_round - 1].image_filename
    yield _sse({
        "type": "done",
        "session_id": session_id,
        "best_round": best_round,
        "final_score": round(best_score, 2),
        "image_b64": _to_b64(best_image),
        "image_url": f"/sessions/{session_id}/{best_filename}",
    })


async def generate_ai_image(session_id: str) -> AsyncIterator[str]:
    """Generate result via wan2.7-image-pro using the session's original image and instruction."""
    session = _store.load_session(session_id)
    original_img = await asyncio.to_thread(_store.load_original_image, session_id)
    reference_img: Optional[Image.Image] = None
    if session.has_reference:
        reference_img = await asyncio.to_thread(_store.load_reference_image, session_id)

    yield _sse({"type": "progress", "status": "ai_generating", "elapsed": 0, "session_id": session_id})

    # Run the blocking API call in a thread; send heartbeat ticks while waiting
    task = asyncio.create_task(
        asyncio.to_thread(wan_edit_image, original_img, session.instruction, reference_img)
    )
    start = asyncio.get_event_loop().time()
    while not task.done():
        await asyncio.sleep(5)
        if not task.done():
            elapsed = int(asyncio.get_event_loop().time() - start)
            yield _sse({"type": "progress", "status": "ai_generating",
                        "elapsed": elapsed, "session_id": session_id})

    try:
        result_img = task.result()
    except Exception as exc:
        yield _sse({"type": "error", "round": 0, "message": f"AI 生图失败：{exc}"})
        return

    filename = await asyncio.to_thread(_store.save_ai_gen_image, session_id, result_img)

    yield _sse({
        "type": "done",
        "session_id": session_id,
        "used_ai_gen": True,
        "image_b64": _to_b64(result_img),
        "image_url": f"/sessions/{session_id}/{filename}",
    })
