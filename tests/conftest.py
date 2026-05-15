import io
import os
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_data_dir(tmp_path, monkeypatch):
    """Redirect data/presets.json to a temp dir for every test."""
    import app.core.preset_store as ps
    monkeypatch.setattr(ps, "DATA_FILE", tmp_path / "presets.json")


@pytest.fixture()
def test_image() -> Image.Image:
    """100×100 solid-color RGB image for processor tests."""
    return Image.new("RGB", (100, 100), color=(120, 80, 60))


@pytest.fixture()
def test_image_path(tmp_path, test_image) -> Path:
    """Save test image to disk and return path."""
    p = tmp_path / "ref.jpg"
    test_image.save(p, "JPEG")
    return p


@pytest.fixture()
def client():
    """FastAPI TestClient with uploads/outputs redirected to tmp dirs."""
    from app.main import app
    with TestClient(app) as c:
        yield c
