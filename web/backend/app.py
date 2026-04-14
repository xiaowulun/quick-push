from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import os

from .routers import api

app = FastAPI(
    title="QuickPush API",
    description="GitHub Trending 智能分析工具 API",
    version="1.0.0"
)

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

app.include_router(api.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


@app.get("/", response_class=HTMLResponse)
async def root():
    if IS_DEV and False:
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get("http://localhost:3000/")
                return HTMLResponse(content=resp.text)
            except:
                pass
    
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
    
    if IS_DEV and False:
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"http://localhost:3000/{path}")
                return HTMLResponse(content=resp.text)
            except:
                pass
    
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
