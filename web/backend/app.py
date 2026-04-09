from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/")
async def root():
    return {"message": "QuickPush API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
