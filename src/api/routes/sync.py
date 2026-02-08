"""同期エンドポイント"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from src.indexer.chunker import Chunker
from src.indexer.image_processor import ImageProcessor
from src.indexer.vector_store import VectorStore
from src.notion.loader import NotionLoader

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncStatus(BaseModel):
    """同期ステータス"""

    status: str
    message: str
    stats: dict | None = None


# グローバルな同期状態
_sync_status = {"running": False, "message": "", "stats": None}


def _run_sync():
    """バックグラウンドで同期を実行"""
    global _sync_status
    _sync_status["running"] = True
    _sync_status["message"] = "同期中..."

    try:
        loader = NotionLoader()
        image_processor = ImageProcessor()
        chunker = Chunker()
        vector_store = VectorStore()

        # ベクトルストアをクリア
        vector_store.clear()

        # ページを読み込み
        pages = loader.load_all_pages()

        total_chunks = 0
        total_images = 0

        for page in pages:
            # 画像を処理
            images = page.images
            for image in images:
                image_processor.process_image(image)
            total_images += len(images)

            # チャンク化
            chunks = chunker.chunk_page(page)
            total_chunks += len(chunks)

            # ベクトルストアに追加
            vector_store.add_chunks(chunks)

        stats = {
            "pages": len(pages),
            "chunks": total_chunks,
            "images": total_images,
        }

        _sync_status["message"] = "同期完了"
        _sync_status["stats"] = stats

    except Exception as e:
        _sync_status["message"] = f"同期エラー: {str(e)}"

    finally:
        _sync_status["running"] = False


@router.post("", response_model=SyncStatus)
async def start_sync(background_tasks: BackgroundTasks) -> SyncStatus:
    """Notionデータの同期を開始"""
    global _sync_status

    if _sync_status["running"]:
        return SyncStatus(
            status="running",
            message="同期が既に実行中です",
        )

    background_tasks.add_task(_run_sync)

    return SyncStatus(
        status="started",
        message="同期を開始しました",
    )


@router.get("/status", response_model=SyncStatus)
async def get_sync_status() -> SyncStatus:
    """同期ステータスを取得"""
    global _sync_status

    if _sync_status["running"]:
        return SyncStatus(
            status="running",
            message=_sync_status["message"],
        )

    return SyncStatus(
        status="idle",
        message=_sync_status["message"],
        stats=_sync_status["stats"],
    )


@router.get("/stats")
async def get_index_stats() -> dict:
    """インデックスの統計情報を取得"""
    vector_store = VectorStore()
    return vector_store.get_stats()
