# Agent Loop (EditingAgent + ReviewAgent) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an iterative AI editing loop where EditingAgent proposes parameters, ReviewAgent scores the result, and the loop continues until quality threshold (≥8.0) or 5 rounds maximum, with every round's image saved and a history viewer in the UI.

**Architecture:** EditingAgent (Claude Vision) → apply existing Pillow/OpenCV pipeline → ReviewAgent (Claude Vision) → feedback injection → repeat. Each round saved to `uploads/sessions/{session_id}/`. Progress streamed via SSE. Frontend adds Agent tab + History tab.

**Tech Stack:** Python 3.11, FastAPI StreamingResponse (SSE), Anthropic SDK (claude-sonnet-4-6), Pillow/OpenCV (existing pipeline), Pydantic v2.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/types/models.py` | Modify | Add AgentEditOutput, ReviewScore, AgentIteration, AgentSession, AgentEditRequest |
| `app/core/editing_agent.py` | Create | Claude Vision call: image+instruction+[reference]+[feedback] → AgentEditOutput |
| `app/core/review_agent.py` | Create | Claude Vision call: original+edited+instruction+[reference] → ReviewScore |
| `app/core/session_store.py` | Create | Save images and history.json per session |
| `app/core/agent_loop.py` | Create | Orchestrate edit→review→iterate, yield SSE strings |
| `app/api/routes_agent.py` | Create | POST /agent/edit (SSE), GET /agent/sessions, GET /agent/sessions/{id} |
| `app/main.py` | Modify | Register agent router, create sessions dir, mount /sessions static |
| `app/static/index.html` | Modify | Agent mode tab + History viewer tab |
| `tests/__init__.py` | Create | Empty, makes tests/ a package |
| `tests/test_review_score.py` | Create | Unit tests for ReviewScore weight calculation |
| `tests/test_session_store.py` | Create | Unit tests for SessionStore persistence logic |

---

### Task 1: Add Agent Models

**Files:**
- Modify: `app/types/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_review_score.py`

- [ ] **Step 1: Write failing test for ReviewScore**

Create `tests/__init__.py` (empty file).

Create `tests/test_review_score.py`:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.types.models import ReviewScore

def test_overall_no_reference():
    score = ReviewScore(visual_quality=6.0, instruction_match=8.0, reference_match=None)
    assert abs(score.overall - (6.0 * 0.35 + 8.0 * 0.65)) < 0.01

def test_overall_with_reference():
    score = ReviewScore(visual_quality=6.0, instruction_match=8.0, reference_match=9.0)
    assert abs(score.overall - (6.0 * 0.25 + 8.0 * 0.40 + 9.0 * 0.35)) < 0.01

def test_is_satisfied_above_threshold():
    score = ReviewScore(visual_quality=9.0, instruction_match=9.0, reference_match=None)
    assert score.is_satisfied is True

def test_is_satisfied_below_threshold():
    score = ReviewScore(visual_quality=7.0, instruction_match=7.0, reference_match=None)
    assert score.is_satisfied is False
```

- [ ] **Step 2: Run test to verify it fails**

```
cd E:\WorkSpace\Zerocc\Private\agent
.venv\Scripts\python -m pytest tests/test_review_score.py -v
```
Expected: ImportError or AttributeError — ReviewScore not defined yet.

- [ ] **Step 3: Append agent models to app/types/models.py**

Append to the bottom of `app/types/models.py`:
```python
# ── Agent loop ────────────────────────────────────────────────────────

class AgentEditOutput(BaseModel):
    """Parameters output by EditingAgent — fed directly into the apply pipeline."""
    edit_params: EditParams = Field(default_factory=EditParams)
    extended_params: ExtendedEditParams = Field(default_factory=ExtendedEditParams)
    portrait_params: PortraitParams = Field(default_factory=PortraitParams)
    background_params: BackgroundParams = Field(default_factory=BackgroundParams)
    curve_params: CurveParams = Field(default_factory=CurveParams)
    explanation: str = ""


class ReviewScore(BaseModel):
    visual_quality: float = Field(ge=0, le=10)
    instruction_match: float = Field(ge=0, le=10)
    reference_match: Optional[float] = Field(None, ge=0, le=10)
    suggestions: dict = Field(default_factory=dict)

    @property
    def overall(self) -> float:
        if self.reference_match is not None:
            return (
                self.visual_quality * 0.25
                + self.instruction_match * 0.40
                + self.reference_match * 0.35
            )
        return self.visual_quality * 0.35 + self.instruction_match * 0.65

    @property
    def is_satisfied(self) -> bool:
        return self.overall >= 8.0


class AgentIteration(BaseModel):
    round: int
    image_filename: str
    params: AgentEditOutput
    scores: dict  # keys: visual_quality, instruction_match, reference_match, overall
    suggestions: dict
    is_satisfied: bool


class AgentSession(BaseModel):
    session_id: str
    instruction: str
    created_at: str
    has_reference: bool
    iterations: List[AgentIteration] = []
    best_round: int = 0


class AgentEditRequest(BaseModel):
    filename: str
    instruction: str
    reference_filename: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv\Scripts\python -m pytest tests/test_review_score.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add app/types/models.py tests/__init__.py tests/test_review_score.py
git commit -m "feat: add agent loop data models (AgentEditOutput, ReviewScore, AgentSession)"
```

---

### Task 2: SessionStore

**Files:**
- Create: `app/core/session_store.py`
- Create: `tests/test_session_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_session_store.py`:
```python
import json, sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.session_store import SessionStore

def test_create_session(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create_session("让照片更暖", has_reference=False)
    assert (tmp_path / sid).is_dir()
    hist = json.loads((tmp_path / sid / "history.json").read_text())
    assert hist["instruction"] == "让照片更暖"
    assert hist["has_reference"] is False

def test_save_and_load_session(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create_session("测试", has_reference=False)
    session = store.load_session(sid)
    assert session.session_id == sid
    assert session.instruction == "测试"

def test_list_sessions(tmp_path):
    store = SessionStore(tmp_path)
    store.create_session("A", has_reference=False)
    store.create_session("B", has_reference=True)
    sessions = store.list_sessions()
    assert len(sessions) == 2

def test_save_iteration_image(tmp_path):
    from PIL import Image
    store = SessionStore(tmp_path)
    sid = store.create_session("test", has_reference=False)
    img = Image.new("RGB", (100, 100), color=(128, 64, 32))
    filename = store.save_iteration_image(sid, round_num=1, score=6.5, img=img)
    assert (tmp_path / sid / filename).exists()
    assert "v1" in filename
    assert "6_5" in filename
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv\Scripts\python -m pytest tests/test_session_store.py -v
```
Expected: ModuleNotFoundError for session_store.

- [ ] **Step 3: Create app/core/session_store.py**

```python
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from PIL import Image

from app.types.models import AgentEditOutput, AgentIteration, AgentSession

SESSIONS_DIR = Path("uploads/sessions")


class SessionStore:
    def __init__(self, base_dir: Path = SESSIONS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, instruction: str, has_reference: bool) -> str:
        sid = uuid.uuid4().hex
        (self.base_dir / sid).mkdir()
        session = AgentSession(
            session_id=sid,
            instruction=instruction,
            created_at=datetime.now().isoformat(),
            has_reference=has_reference,
        )
        self._write(session)
        return sid

    def load_session(self, session_id: str) -> AgentSession:
        path = self.base_dir / session_id / "history.json"
        return AgentSession(**json.loads(path.read_text(encoding="utf-8")))

    def save_session(self, session: AgentSession) -> None:
        self._write(session)

    def list_sessions(self) -> List[AgentSession]:
        sessions = []
        for d in sorted(self.base_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            hist = d / "history.json"
            if hist.exists():
                try:
                    sessions.append(AgentSession(**json.loads(hist.read_text(encoding="utf-8"))))
                except Exception:
                    pass
        return sessions

    def save_iteration_image(self, session_id: str, round_num: int, score: float, img: Image.Image) -> str:
        score_str = f"{score:.1f}".replace(".", "_")
        filename = f"v{round_num}_score{score_str}.jpg"
        img.convert("RGB").save(self.base_dir / session_id / filename, "JPEG", quality=92, optimize=True)
        return filename

    def save_original(self, session_id: str, img: Image.Image) -> None:
        img.convert("RGB").save(self.base_dir / session_id / "original.jpg", "JPEG", quality=92)

    def save_reference(self, session_id: str, img: Image.Image) -> None:
        img.convert("RGB").save(self.base_dir / session_id / "ref.jpg", "JPEG", quality=92)

    def _write(self, session: AgentSession) -> None:
        path = self.base_dir / session.session_id / "history.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_session_store.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add app/core/session_store.py tests/test_session_store.py
git commit -m "feat: add SessionStore for per-session image and history persistence"
```

---

### Task 3: EditingAgent

**Files:**
- Create: `app/core/editing_agent.py`

- [ ] **Step 1: Create app/core/editing_agent.py**

```python
import base64
import io
import json
import os
from typing import Optional

import anthropic
from PIL import Image

from app.types.models import (
    AgentEditOutput, BackgroundParams, CurveParams,
    EditParams, ExtendedEditParams, PortraitParams, ReviewScore,
)

_SYSTEM_FIRST = """You are an expert photo retouching assistant. Analyze the image(s) and instruction, then return ONLY a valid JSON object.

Return exactly this structure:
{
  "edit_params": {
    "brightness": <float 0.5-2.0, 1.0=unchanged>,
    "contrast": <float 0.5-2.0, 1.0=unchanged>,
    "saturation": <float 0.5-2.0, 1.0=unchanged>,
    "sharpness": <float 0.5-2.0, 1.0=unchanged>,
    "color_temp": <int -100 to 100, 0=neutral, positive=warm, negative=cool>
  },
  "extended_params": {
    "highlights": <int -100 to 100>,
    "shadows": <int -100 to 100>,
    "whites": <int -100 to 100>,
    "blacks": <int -100 to 100>,
    "vibrance": <int -60 to 60>,
    "clarity": <int -60 to 60>,
    "vignette": <int -100 to 100>,
    "grain": <int 0 to 100>,
    "shadow_tint": <int 0 to 360>,
    "shadow_tint_strength": <int 0 to 100>,
    "highlight_tint": <int 0 to 360>,
    "highlight_tint_strength": <int 0 to 100>
  },
  "portrait_params": {
    "smooth_skin": <bool>,
    "smooth_level": <float 0.0-1.0>,
    "brighten_skin": <bool>,
    "brighten_level": <float 0.0-1.0>
  },
  "background_params": {
    "action": <"none"|"blur"|"remove">,
    "blur_radius": <int 5-30>
  },
  "curve_params": {
    "rgb": [[0,0],[255,255]],
    "r": [[0,0],[255,255]],
    "g": [[0,0],[255,255]],
    "b": [[0,0],[255,255]]
  },
  "explanation": "<one sentence in Chinese explaining what you changed>"
}

Keep edits natural and subtle. Output JSON only."""

_SYSTEM_FEEDBACK = """You are an expert photo retouching assistant refining a previous edit based on reviewer feedback.

Adjust ONLY the parameters flagged as problematic. Do not change dimensions that were already rated well (score >= 8).

Return the same JSON structure with your refined parameters. Output JSON only."""


def _img_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def _parse(text: str) -> AgentEditOutput:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    data = json.loads(text)
    return AgentEditOutput(
        edit_params=EditParams(**data.get("edit_params", {})),
        extended_params=ExtendedEditParams(**data.get("extended_params", {})),
        portrait_params=PortraitParams(**data.get("portrait_params", {})),
        background_params=BackgroundParams(**data.get("background_params", {})),
        curve_params=CurveParams(**data.get("curve_params", {})),
        explanation=data.get("explanation", ""),
    )


def run_editing_agent(
    original_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
    previous_output: Optional[AgentEditOutput] = None,
    review_score: Optional[ReviewScore] = None,
) -> AgentEditOutput:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)
    is_first = previous_output is None

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(original_img)}},
        {"type": "text", "text": "原始图片"},
    ]

    if reference_img is not None:
        content += [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(reference_img)}},
            {"type": "text", "text": "参考图片（请让效果尽量接近此风格）"},
        ]

    if is_first:
        user_text = f"用户指令：{instruction}"
    else:
        sugg_lines = "\n".join(f"  - {k}: {v}" for k, v in (review_score.suggestions if review_score else {}).items())
        user_text = (
            f"用户指令：{instruction}\n\n"
            f"上一轮参数：\n{previous_output.model_dump_json(indent=2)}\n\n"
            f"审查反馈（请针对以下问题调整，不要大幅改动已合格的维度）：\n{sugg_lines}"
        )

    content.append({"type": "text", "text": user_text})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM_FIRST if is_first else _SYSTEM_FEEDBACK,
        messages=[{"role": "user", "content": content}],
    )
    return _parse(response.content[0].text)
```

- [ ] **Step 2: Verify syntax**

```
.venv\Scripts\python -c "from app.core.editing_agent import run_editing_agent; print('OK')"
```
Expected: OK

- [ ] **Step 3: Commit**

```
git add app/core/editing_agent.py
git commit -m "feat: add EditingAgent with first-round and feedback-injection modes"
```

---

### Task 4: ReviewAgent

**Files:**
- Create: `app/core/review_agent.py`

- [ ] **Step 1: Create app/core/review_agent.py**

```python
import base64
import io
import json
import os
from typing import Optional

import anthropic
from PIL import Image

from app.types.models import ReviewScore

_SYSTEM = """You are a professional photo quality reviewer. Compare the photos provided and score the edit.

Return ONLY a valid JSON object:
{
  "scores": {
    "visual_quality": <float 0-10>,
    "instruction_match": <float 0-10>,
    "reference_match": <float 0-10 or null if no reference>
  },
  "suggestions": {
    "visual_quality": "<specific fix in Chinese, or empty string if score >= 8>",
    "instruction_match": "<specific fix in Chinese, or empty string if score >= 8>",
    "reference_match": "<specific fix in Chinese, or empty string if no reference or score >= 8>"
  }
}

Scoring criteria:
- visual_quality: Is the result natural? No overexposure, color cast, halos, or artifacts?
- instruction_match: Did the edit accomplish what the user instruction asked for?
- reference_match: How closely does the edit's style match the reference image? (null if no reference provided)

Be specific in suggestions — name the exact parameter to adjust and the direction.
Output JSON only."""


def _img_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def run_review_agent(
    original_img: Image.Image,
    edited_img: Image.Image,
    instruction: str,
    reference_img: Optional[Image.Image] = None,
    round_num: int = 1,
) -> ReviewScore:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(original_img)}},
        {"type": "text", "text": "原始图片"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(edited_img)}},
        {"type": "text", "text": f"第{round_num}轮修图结果"},
    ]

    if reference_img is not None:
        content += [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(reference_img)}},
            {"type": "text", "text": "参考图片（目标风格）"},
        ]

    content.append({"type": "text", "text": f"用户指令：{instruction}\n\n请评分并给出改进建议。"})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )

    text = response.content[0].text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

    data = json.loads(text)
    scores = data.get("scores", {})
    suggestions = {k: v for k, v in data.get("suggestions", {}).items() if v}

    ref_raw = scores.get("reference_match")
    return ReviewScore(
        visual_quality=float(scores.get("visual_quality", 5.0)),
        instruction_match=float(scores.get("instruction_match", 5.0)),
        reference_match=float(ref_raw) if ref_raw is not None else None,
        suggestions=suggestions,
    )
```

- [ ] **Step 2: Verify syntax**

```
.venv\Scripts\python -c "from app.core.review_agent import run_review_agent; print('OK')"
```
Expected: OK

- [ ] **Step 3: Commit**

```
git add app/core/review_agent.py
git commit -m "feat: add ReviewAgent with three-dimension scoring (visual, instruction, reference)"
```

---

### Task 5: AgentLoop Orchestrator

**Files:**
- Create: `app/core/agent_loop.py`

- [ ] **Step 1: Create app/core/agent_loop.py**

```python
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
```

- [ ] **Step 2: Verify syntax**

```
.venv\Scripts\python -c "from app.core.agent_loop import run_agent_loop; print('OK')"
```
Expected: OK

- [ ] **Step 3: Commit**

```
git add app/core/agent_loop.py
git commit -m "feat: add AgentLoop orchestrator with SSE streaming and best-score tracking"
```

---

### Task 6: API Routes + Wire up main.py

**Files:**
- Create: `app/api/routes_agent.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create app/api/routes_agent.py**

```python
import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from app.core.agent_loop import run_agent_loop
from app.core.session_store import SessionStore
from app.types.models import AgentEditRequest

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
```

- [ ] **Step 2: Modify app/main.py**

In `app/main.py`, after the existing `from app.api.routes import router` line, add:
```python
from app.api.routes_agent import router as agent_router
```

After `Path("data").mkdir(exist_ok=True)`, add:
```python
Path("uploads/sessions").mkdir(parents=True, exist_ok=True)
```

After `app.include_router(router, prefix="/api")`, add:
```python
app.include_router(agent_router, prefix="/api")
```

After `app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")`, add:
```python
app.mount("/sessions", StaticFiles(directory="uploads/sessions"), name="sessions")
```

- [ ] **Step 3: Verify server imports**

```
.venv\Scripts\python -c "from app.main import app; print('OK')"
```
Expected: OK

- [ ] **Step 4: Commit**

```
git add app/api/routes_agent.py app/main.py
git commit -m "feat: add agent API routes (POST /agent/edit SSE, GET /agent/sessions)"
```

---

### Task 7: Frontend — Agent Mode Tab

**Files:**
- Modify: `app/static/index.html`

The goal is to add an "Agent 修图" tab that shows real-time round progress with thumbnails and scores.

- [ ] **Step 1: Add tab button**

In `app/static/index.html`, find the tab navigation bar (look for existing tab buttons like "手动调整", "AI 智能" etc.) and add a new tab button:
```html
<button class="tab-btn" onclick="switchTab('agent')">Agent 修图</button>
```

- [ ] **Step 2: Add agent panel HTML**

Find where other panel `<div>`s are defined and add:
```html
<!-- Agent Mode Panel -->
<div id="agentPanel" class="panel" style="display:none">
  <div class="section-card">
    <h3 style="margin:0 0 8px">Agent 智能修图</h3>
    <p style="color:#aaa;font-size:13px;margin:0 0 14px">AI 自动迭代优化，每轮由审查 Agent 评分，直到满意为止（最多5轮）</p>

    <label style="font-size:13px;color:#ccc">修图指令</label>
    <input id="agentInstruction" type="text" placeholder="例如：让照片更暖更通透"
           style="width:100%;margin-top:6px;padding:8px 10px;background:#2a2a2a;border:1px solid #444;border-radius:6px;color:#fff;font-size:14px;box-sizing:border-box">

    <button id="agentStartBtn" onclick="startAgentEdit()"
            style="margin-top:12px;width:100%;padding:10px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border:none;border-radius:8px;color:#fff;font-size:14px;cursor:pointer;font-weight:600">
      开始 Agent 修图
    </button>
  </div>

  <div id="agentProgress" class="section-card" style="display:none">
    <h4 style="margin:0 0 12px;color:#e5e7eb">修图进度</h4>
    <div id="agentRounds"></div>
  </div>

  <div id="agentResult" class="section-card" style="display:none">
    <h4 style="margin:0 0 12px;color:#e5e7eb">最终结果</h4>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div>
        <p style="font-size:12px;color:#6b7280;margin:0 0 6px">原图</p>
        <img id="agentOriginalPreview" style="width:100%;border-radius:8px">
      </div>
      <div>
        <p style="font-size:12px;color:#6b7280;margin:0 0 6px">最佳结果</p>
        <img id="agentBestPreview" style="width:100%;border-radius:8px">
      </div>
    </div>
    <p id="agentBestInfo" style="margin-top:10px;font-size:13px;color:#9ca3af"></p>
    <button onclick="applyAgentResult()"
            style="margin-top:10px;padding:8px 18px;background:#059669;border:none;border-radius:6px;color:#fff;cursor:pointer;font-size:14px">
      应用此结果
    </button>
  </div>
</div>
```

- [ ] **Step 3: Add agent JS**

Before the closing `</body>` tag, add:
```html
<script>
let agentBestImageUrl = null;

function startAgentEdit() {
  const instruction = document.getElementById('agentInstruction').value.trim();
  if (!instruction) { alert('请输入修图指令'); return; }
  if (!currentFilename) { alert('请先上传图片'); return; }

  document.getElementById('agentProgress').style.display = 'block';
  document.getElementById('agentResult').style.display = 'none';
  document.getElementById('agentRounds').innerHTML = '';
  document.getElementById('agentStartBtn').disabled = true;
  document.getElementById('agentStartBtn').textContent = '修图中...';
  agentBestImageUrl = null;

  const body = { filename: currentFilename, instruction };
  if (typeof referenceFilename !== 'undefined' && referenceFilename) {
    body.reference_filename = referenceFilename;
  }

  fetch('/api/agent/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(async res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        if (part.startsWith('data: ')) {
          try { handleAgentEvent(JSON.parse(part.slice(6))); } catch(e) {}
        }
      }
    }
  }).catch(err => {
    alert('Agent 修图失败: ' + err.message);
  }).finally(() => {
    document.getElementById('agentStartBtn').disabled = false;
    document.getElementById('agentStartBtn').textContent = '开始 Agent 修图';
  });
}

function handleAgentEvent(evt) {
  if (evt.type === 'progress' && evt.status === 'editing') {
    _addRoundCard(evt.round, '修图中...', null, null, null, false);
  } else if (evt.type === 'progress' && evt.status === 'reviewing') {
    _updateRoundStatus(evt.round, '审查中...');
  } else if (evt.type === 'progress' && evt.status === 'done_round') {
    _updateRoundCard(evt.round, evt.explanation, evt.score, evt.image_url, evt.suggestions, evt.is_satisfied);
  } else if (evt.type === 'done') {
    agentBestImageUrl = evt.image_url;
    document.getElementById('agentResult').style.display = 'block';
    document.getElementById('agentOriginalPreview').src = '/uploads/' + currentFilename;
    document.getElementById('agentBestPreview').src = evt.image_url;
    document.getElementById('agentBestInfo').textContent =
      `最佳结果：第 ${evt.best_round} 轮，综合评分 ${evt.final_score.toFixed(1)} / 10`;
  }
}

function _addRoundCard(round, statusText, score, imageUrl, suggestions, satisfied) {
  if (document.getElementById('round-card-' + round)) return;
  const div = document.createElement('div');
  div.id = 'round-card-' + round;
  div.style.cssText = 'background:#1e1e1e;border-radius:8px;padding:12px;margin-bottom:10px;border:1px solid #333';
  div.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span style="font-weight:bold;color:#a78bfa">第 ${round} 轮</span>
      <span id="round-status-${round}" style="font-size:13px;color:#6b7280">${statusText}</span>
      <span id="round-score-${round}" style="margin-left:auto;font-size:13px"></span>
    </div>
    <div id="round-body-${round}"></div>`;
  document.getElementById('agentRounds').appendChild(div);
}

function _updateRoundStatus(round, text) {
  const el = document.getElementById('round-status-' + round);
  if (el) el.textContent = text;
}

function _updateRoundCard(round, explanation, score, imageUrl, suggestions, satisfied) {
  _addRoundCard(round, explanation || '', score, imageUrl, suggestions, satisfied);
  document.getElementById('round-status-' + round).textContent = explanation || '';
  const scoreEl = document.getElementById('round-score-' + round);
  if (score !== null) {
    scoreEl.textContent = `${score.toFixed(1)} / 10${satisfied ? ' ✓' : ''}`;
    scoreEl.style.color = satisfied ? '#34d399' : score >= 7 ? '#fbbf24' : '#f87171';
  }
  const body = document.getElementById('round-body-' + round);
  let html = imageUrl ? `<img src="${imageUrl}" style="width:100%;max-height:180px;object-fit:cover;border-radius:6px">` : '';
  if (suggestions && Object.keys(suggestions).length) {
    html += `<div style="margin-top:8px;font-size:12px;color:#9ca3af;line-height:1.6">`;
    for (const [, v] of Object.entries(suggestions)) html += `<div>· ${v}</div>`;
    html += `</div>`;
  }
  body.innerHTML = html;
}

function applyAgentResult() {
  if (!agentBestImageUrl) return;
  const resultImg = document.getElementById('resultImage');
  if (resultImg) { resultImg.src = agentBestImageUrl; resultImg.style.display = 'block'; }
}
</script>
```

- [ ] **Step 4: Commit**

```
git add app/static/index.html
git commit -m "feat: add Agent mode tab with real-time round cards and SSE progress"
```

---

### Task 8: Frontend — History Viewer Tab

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add history tab button**

Add next to the Agent tab button:
```html
<button class="tab-btn" onclick="switchTab('history'); loadHistory();">历史记录</button>
```

- [ ] **Step 2: Add history panel HTML**

```html
<!-- History Panel -->
<div id="historyPanel" class="panel" style="display:none">
  <div class="section-card" style="display:flex;justify-content:space-between;align-items:center">
    <h3 style="margin:0">历史记录</h3>
    <button onclick="loadHistory()"
            style="padding:6px 14px;background:#374151;border:none;border-radius:6px;color:#fff;cursor:pointer;font-size:13px">
      刷新
    </button>
  </div>

  <div id="historyList"></div>

  <!-- Detail view (hidden until a session is clicked) -->
  <div id="historyDetail" style="display:none">
    <div class="section-card">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <button onclick="closeHistoryDetail()"
                style="padding:4px 10px;background:#374151;border:none;border-radius:5px;color:#fff;cursor:pointer">
          ← 返回
        </button>
        <h4 id="historyDetailTitle" style="margin:0;flex:1;color:#e5e7eb"></h4>
      </div>

      <div id="historyRoundGrid"
           style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px"></div>

      <!-- Compare view -->
      <div id="historyCompare" style="display:none;margin-top:16px">
        <h4 style="margin:0 0 10px;color:#e5e7eb">版本对比</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div style="text-align:center">
            <img id="compareLeft" style="width:100%;border-radius:8px">
            <p id="compareLeftLabel" style="font-size:12px;color:#9ca3af;margin-top:6px"></p>
          </div>
          <div style="text-align:center">
            <img id="compareRight" style="width:100%;border-radius:8px">
            <p id="compareRightLabel" style="font-size:12px;color:#9ca3af;margin-top:6px"></p>
          </div>
        </div>
        <button onclick="document.getElementById('historyCompare').style.display='none';compareLeftPending=null"
                style="margin-top:10px;padding:6px 14px;background:#374151;border:none;border-radius:6px;color:#fff;cursor:pointer;font-size:13px">
          关闭对比
        </button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add history JS**

```html
<script>
let compareLeftPending = null;

async function loadHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '<p style="color:#6b7280;padding:12px">加载中...</p>';
  const res = await fetch('/api/agent/sessions');
  const data = await res.json();
  list.innerHTML = '';

  if (!data.sessions.length) {
    list.innerHTML = '<p style="color:#6b7280;padding:12px">暂无历史记录</p>';
    return;
  }

  for (const s of data.sessions) {
    const scoreText = s.best_score !== null ? ` · 最高分 ${s.best_score.toFixed(1)}` : '';
    const div = document.createElement('div');
    div.className = 'section-card';
    div.style.cssText = 'display:flex;align-items:center;justify-content:space-between;cursor:pointer;margin-bottom:8px';
    div.innerHTML = `
      <div>
        <div style="font-weight:600;color:#e5e7eb">${s.instruction}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:3px">
          ${new Date(s.created_at).toLocaleString()} · ${s.total_rounds} 轮${scoreText}
        </div>
      </div>
      <span style="color:#7c3aed;font-size:22px;line-height:1">›</span>`;
    div.onclick = () => openHistoryDetail(s.session_id, s.instruction);
    list.appendChild(div);
  }
}

async function openHistoryDetail(sessionId, instruction) {
  const res = await fetch('/api/agent/sessions/' + sessionId);
  const session = await res.json();

  document.getElementById('historyDetail').style.display = 'block';
  document.getElementById('historyDetailTitle').textContent = instruction;
  document.getElementById('historyCompare').style.display = 'none';
  compareLeftPending = null;

  const grid = document.getElementById('historyRoundGrid');
  grid.innerHTML = '';

  for (const iter of session.iterations) {
    const imageUrl = '/sessions/' + sessionId + '/' + iter.image_filename;
    const overall = iter.scores.overall;
    const isBest = iter.round === session.best_round;

    const card = document.createElement('div');
    card.style.cssText = `background:#1e1e1e;border-radius:8px;overflow:hidden;border:2px solid ${isBest ? '#7c3aed' : '#333'}`;
    card.innerHTML = `
      <img src="${imageUrl}" style="width:100%;height:110px;object-fit:cover;display:block">
      <div style="padding:8px">
        <div style="font-size:12px;color:#e5e7eb;font-weight:600">第${iter.round}轮 ${isBest ? '⭐' : ''}</div>
        <div style="font-size:12px;color:#34d399">评分 ${overall.toFixed(1)}</div>
        <button onclick="selectForCompare(${iter.round},'${imageUrl}')"
                style="margin-top:6px;width:100%;padding:3px 0;font-size:11px;background:#374151;border:none;border-radius:4px;color:#d1d5db;cursor:pointer">
          选择对比
        </button>
      </div>`;
    grid.appendChild(card);
  }
  document.getElementById('historyDetail').scrollIntoView({ behavior: 'smooth' });
}

function selectForCompare(round, imageUrl) {
  if (!compareLeftPending) {
    compareLeftPending = { round, imageUrl };
    document.getElementById('compareLeft').src = imageUrl;
    document.getElementById('compareLeftLabel').textContent = `第${round}轮（点击另一张完成对比）`;
    document.getElementById('compareRight').src = '';
    document.getElementById('compareRightLabel').textContent = '请选择第二张';
    document.getElementById('historyCompare').style.display = 'block';
  } else {
    document.getElementById('compareRight').src = imageUrl;
    document.getElementById('compareRightLabel').textContent = `第${round}轮`;
    document.getElementById('compareLeftLabel').textContent = `第${compareLeftPending.round}轮`;
    compareLeftPending = null;
  }
}

function closeHistoryDetail() {
  document.getElementById('historyDetail').style.display = 'none';
  document.getElementById('historyCompare').style.display = 'none';
  compareLeftPending = null;
}
</script>
```

- [ ] **Step 4: Commit**

```
git add app/static/index.html
git commit -m "feat: add history viewer tab with session list, round grid, and compare mode"
```

---

## Self-Review

### Spec coverage:
- ✅ EditingAgent: first-round and feedback-injection modes
- ✅ ReviewAgent: visual_quality + instruction_match + reference_match (weighted)
- ✅ Dynamic loop: stops at overall ≥ 8.0 or 5 rounds, returns highest-scored result
- ✅ Every iteration image saved with round number + score in filename
- ✅ history.json updated after each round with full params + scores + suggestions
- ✅ SSE streaming: editing → reviewing → done_round events per round, then done
- ✅ GET /agent/sessions: lists all sessions with summary
- ✅ GET /agent/sessions/{id}: returns full session data including all iterations
- ✅ /sessions/ static mount for serving per-round images
- ✅ Agent tab: real-time round cards with thumbnail + score + suggestions
- ✅ History tab: session list → detail → round grid → compare any two versions
- ✅ "Apply best result" button in agent tab

### Type consistency:
- `AgentEditOutput` defined in Task 1, used as `iteration.params` in Task 5, returned by `run_editing_agent` in Task 3
- `ReviewScore.overall` / `.is_satisfied` are Python `@property` — accessed in agent_loop.py correctly
- `AgentIteration.scores["overall"]` set from `review.overall` in agent_loop.py, read in routes_agent.py for best_score
- `image_filename` from `save_iteration_image()` stored in `AgentIteration.image_filename`, used to build URL as `/sessions/{session_id}/{image_filename}` — consistent across agent_loop.py and frontend JS
