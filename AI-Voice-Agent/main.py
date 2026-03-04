"""
Enterprise Voice AI Gateway — Main Application
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import settings
from database import init_db
from chat_router import router as chat_router
from admin_api import router as admin_router


# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.app_name} starting…")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Gateway shutting down")


# ── App ───────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade AI Voice Gateway — powered by Twilio, Whisper & OpenAI",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static & Templates ────────────────────────────────────
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Routers ───────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(admin_router)


# ── Dashboard ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    html_path = static_dir / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard not found. Run setup.</h1>", status_code=503)

@app.get("/chat", response_class=HTMLResponse)
async def customer_chat(request: Request):
    html_path = static_dir / "chat.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Chat UI not found</h1>", status_code=503)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.app_name, "version": "2.0.0"}


# ── Entry Point ───────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
