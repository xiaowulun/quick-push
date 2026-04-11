from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from .routers import api

app = FastAPI(
    title="QuickPush API",
    description="GitHub Trending 智能分析工具 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端HTML页面"""
    html_file = FRONTEND_DIR / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)

@app.get("/health")
async def health():
    return {"status": "healthy"}

# 挂载静态文件目录
STATIC_DIR = FRONTEND_DIR / "statics"
if STATIC_DIR.exists():
    app.mount("/statics", StaticFiles(directory=str(STATIC_DIR)), name="statics")
