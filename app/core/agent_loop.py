import asyncio
import base64
import io
import json
from typing import AsyncIterator, Optional

from PIL import Image

from app.core.background import apply_background
from app.core.curve_processor import apply_curves
from app.core.editing_agent import run_editing_agent
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

    session = _store.load_session(session_id)
    previous_output: Optional[AgentEditOutput] = None
    previous_review: Optional[ReviewScore] = None
    best_round = 0
    best_score = -1.0
    best_image: Optional[Image.Image] = None

    for round_num in range(1, MAX_ROUNDS + 1):
        yield _sse({"type": "progress", "round": round_num, "status": "editing", "session_id": session_id})

        edit_output = await asyncio.to_thread(
            run_editing_agent, original_img, instruction, reference_img, previous_output, previous_review,
        )
        edited_img = await asyncio.to_thread(_apply_params, original_img, edit_output)

        yield _sse({"type": "progress", "round": round_num, "status": "reviewing", "session_id": session_id})

        review = await asyncio.to_thread(
            run_review_agent, original_img, edited_img, instruction, reference_img, round_num,
        )

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
