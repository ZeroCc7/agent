import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image

from app.types.models import AgentSession

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

    def load_original_image(self, session_id: str) -> Image.Image:
        return Image.open(self.base_dir / session_id / "original.jpg").convert("RGB")

    def load_reference_image(self, session_id: str) -> Optional[Image.Image]:
        path = self.base_dir / session_id / "ref.jpg"
        if not path.exists():
            return None
        return Image.open(path).convert("RGB")

    def load_best_image(self, session_id: str) -> Image.Image:
        session = self.load_session(session_id)
        if not session.iterations or session.best_round == 0:
            return self.load_original_image(session_id)
        filename = session.iterations[session.best_round - 1].image_filename
        return Image.open(self.base_dir / session_id / filename).convert("RGB")

    def save_ai_gen_image(self, session_id: str, img: Image.Image) -> str:
        ts = datetime.now().strftime("%H%M%S")
        filename = f"ai_gen_{ts}.jpg"
        img.convert("RGB").save(self.base_dir / session_id / filename, "JPEG", quality=92, optimize=True)
        return filename

    def _write(self, session: AgentSession) -> None:
        path = self.base_dir / session.session_id / "history.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
