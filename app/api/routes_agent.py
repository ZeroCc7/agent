import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from app.core.agent_loop import continue_agent_loop, generate_ai_image, run_agent_loop
from app.core.session_store import SessionStore
from app.types.models import AgentContinueRequest, AgentEditRequest, AgentGenerateRequest

router = APIRouter()
UPLOAD_DIR = Path("uploads")
_store = SessionStore()


@router.post("/agent/edit")
async def agent_edit(request: AgentEditRequest):
    src = UPLOAD_DIR / request.filename
    if not src.exists():
        raise HTTPException(404, "图片不存在，请重新上传")
    if not request.instruction.strip():
        raise HTTPException(400, "请描述你想要的效果")

    original_img = Image.open(src).convert("RGB")
    reference_img = None
    if request.reference_filename:
        ref_path = UPLOAD_DIR / request.reference_filename
        if not ref_path.exists():
            raise HTTPException(404, "参考图不存在")
        reference_img = Image.open(ref_path).convert("RGB")

    async def event_stream():
        async for chunk in run_agent_loop(original_img, request.instruction, reference_img):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/agent/continue")
async def agent_continue(request: AgentContinueRequest):
    try:
        session = await asyncio.to_thread(_store.load_session, request.session_id)
    except Exception:
        raise HTTPException(404, "Session 不存在")
    if not session.iterations:
        raise HTTPException(400, "Session 尚无轮次记录，请先运行 Agent 修图")

    async def event_stream():
        async for chunk in continue_agent_loop(request.session_id, request.extra_rounds):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/agent/generate")
async def agent_generate(request: AgentGenerateRequest):
    try:
        await asyncio.to_thread(_store.load_session, request.session_id)
    except Exception:
        raise HTTPException(404, "Session 不存在")

    async def event_stream():
        async for chunk in generate_ai_image(request.session_id):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/agent/sessions")
async def list_sessions():
    sessions = await asyncio.to_thread(_store.list_sessions)
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "instruction": s.instruction,
                "created_at": s.created_at,
                "has_reference": s.has_reference,
                "best_round": s.best_round,
                "total_rounds": len(s.iterations),
                "best_score": (
                    s.iterations[s.best_round - 1].scores["overall"]
                    if s.iterations and s.best_round > 0
                    else None
                ),
            }
            for s in sessions
        ]
    }


@router.get("/agent/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = await asyncio.to_thread(_store.load_session, session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session 不存在")
    return session.model_dump()
