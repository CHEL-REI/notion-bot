"""ChromaDB操作"""

import json

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config.settings import get_settings
from src.indexer.chunker import Chunk
from src.indexer.embedder import Embedder


class VectorStore:
    """ChromaDBを使ったベクトルストア"""

    COLLECTION_NAME = "notion_pages"

    def __init__(self):
        settings = get_settings()
        self.persist_dir = settings.chroma_persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = Embedder()

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """チャンクをベクトルストアに追加"""
        if not chunks:
            return

        # テキストをベクトル化
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)

        # ChromaDBに追加
        ids = [chunk.id for chunk in chunks]
        documents = texts
        metadatas = [
            {
                "page_id": chunk.page_id,
                "page_title": chunk.page_title,
                "page_url": chunk.page_url,
                "image_paths": json.dumps(chunk.image_paths),
                "section_index": chunk.metadata.get("section_index", 0),
            }
            for chunk in chunks
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """クエリに類似するチャンクを検索"""
        query_embedding = self.embedder.embed(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        # 結果を整形
        search_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0

                # image_pathsをJSONからリストに変換
                image_paths = json.loads(metadata.get("image_paths", "[]"))

                search_results.append({
                    "text": doc,
                    "page_id": metadata.get("page_id", ""),
                    "page_title": metadata.get("page_title", ""),
                    "page_url": metadata.get("page_url", ""),
                    "image_paths": image_paths,
                    "score": 1 - distance,  # コサイン類似度に変換
                })

        return search_results

    def clear(self) -> None:
        """コレクションをクリア"""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def get_stats(self) -> dict:
        """ベクトルストアの統計情報を取得"""
        return {
            "total_chunks": self.collection.count(),
        }
