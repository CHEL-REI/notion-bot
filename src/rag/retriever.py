"""検索ロジック"""

from src.indexer.vector_store import VectorStore


class Retriever:
    """ベクトルストアから関連ドキュメントを検索"""

    def __init__(self, top_k: int = 5):
        self.vector_store = VectorStore()
        self.top_k = top_k

    def retrieve(self, query: str) -> list[dict]:
        """クエリに関連するドキュメントを検索"""
        return self.vector_store.search(query, top_k=self.top_k)

    def retrieve_with_threshold(
        self, query: str, score_threshold: float = 0.5
    ) -> list[dict]:
        """スコア閾値を超えるドキュメントのみを検索"""
        results = self.retrieve(query)
        return [r for r in results if r.get("score", 0) >= score_threshold]
