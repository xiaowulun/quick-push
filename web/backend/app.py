import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.infrastructure.logging import get_logger, reset_request_id, set_request_id
from .routers import api


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Initialize chat/search services early so reranker/index warmup starts before first user request.
    api.warmup_runtime_services()
    yield


app = FastAPI(
    title="QuickPush API",
    description="GitHub Trending 智能分析工具 API",
    version="1.0.0",
    lifespan=lifespan,
)
logger = get_logger(__name__)

IS_DEV = os.getenv("NODE_ENV") != "production"

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if IS_DEV else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = set_request_id(request_id)
    started = perf_counter()
    method = request.method
    path = request.url.path
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = int((perf_counter() - started) * 1000)
        logger.exception(
            "HTTP request failed %s %s",
            method,
            path,
            extra={"latency_ms": latency_ms},
        )
        reset_request_id(token)
        raise

    latency_ms = int((perf_counter() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "HTTP request completed %s %s -> %s",
        method,
        path,
        response.status_code,
        extra={"latency_ms": latency_ms},
    )
    reset_request_id(token)
    return response

app.include_router(api.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = DIST_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    
    html_file = FRONTEND_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/{path:path}", response_class=HTMLResponse)
async def spa_fallback(path: str):
    if path.startswith("api/") or path.startswith("@"):
        return HTMLResponse(content="Not found", status_code=404)

    file_path = DIST_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    html_file = DIST_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    
    return HTMLResponse(content="Not found", status_code=404)


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

STATIC_DIR = FRONTEND_DIR / "statics"
if STATIC_DIR.exists():
    app.mount("/statics", StaticFiles(directory=str(STATIC_DIR)), name="statics")
