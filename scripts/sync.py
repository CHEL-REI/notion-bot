#!/usr/bin/env python
"""Notionデータ同期スクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.indexer.chunker import Chunker
from src.indexer.image_processor import ImageProcessor
from src.indexer.vector_store import VectorStore
from src.notion.loader import NotionLoader


def sync_notion_data():
    """Notionデータを同期してインデックスを構築"""
    print("=== Notion同期開始 ===\n")

    # 初期化
    loader = NotionLoader()
    image_processor = ImageProcessor()
    chunker = Chunker()
    vector_store = VectorStore()

    # ベクトルストアをクリア（フル同期）
    print("既存のインデックスをクリア...")
    vector_store.clear()

    # ページを読み込み
    print("Notionからページを読み込み中...")
    pages = loader.load_all_pages()
    print(f"  {len(pages)}ページを取得\n")

    total_chunks = 0
    total_images = 0

    for page in pages:
        print(f"処理中: {page.title}")

        # 画像を処理
        images = page.images
        if images:
            print(f"  画像: {len(images)}枚")
            for i, image in enumerate(images):
                print(f"    [{i+1}/{len(images)}] 処理中...")
                image_processor.process_image(image)
            total_images += len(images)

        # チャンク化
        chunks = chunker.chunk_page(page)
        print(f"  チャンク: {len(chunks)}個")
        total_chunks += len(chunks)

        # ベクトルストアに追加
        vector_store.add_chunks(chunks)

    # 統計情報
    stats = vector_store.get_stats()
    print("\n=== 同期完了 ===")
    print(f"処理ページ数: {len(pages)}")
    print(f"総チャンク数: {total_chunks}")
    print(f"処理画像数: {total_images}")
    print(f"インデックス内チャンク数: {stats['total_chunks']}")


if __name__ == "__main__":
    sync_notion_data()
