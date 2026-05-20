from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.api.routes import router
from app.api.routes_agent import router as agent_router

app = FastAPI(title="AI 照片美化", description="Intelligent photo retouching assistant")

Path("uploads").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)
Path("uploads/sessions").mkdir(parents=True, exist_ok=True)

app.include_router(router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/sessions", StaticFiles(directory="uploads/sessions"), name="sessions")


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path("app/static/index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
