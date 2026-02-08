"""FastAPIアプリケーション"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import chat, settings, sync
from src.config.settings import get_settings

app = FastAPI(
    title="Notion Chatbot API",
    description="Notionページを読み込み質問に答えるチャットボットAPI",
    version="0.1.0",
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(chat.router)
app.include_router(sync.router)
app.include_router(settings.router)

# 画像ファイルを静的ファイルとして提供
settings = get_settings()
settings.image_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(settings.image_storage_dir)), name="images")


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "name": "Notion Chatbot API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "healthy"}
