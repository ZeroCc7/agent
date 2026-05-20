import json, sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.session_store import SessionStore

def test_create_session(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create_session("让照片更暖", has_reference=False)
    assert (tmp_path / sid).is_dir()
    hist = json.loads((tmp_path / sid / "history.json").read_text(encoding="utf-8"))
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
