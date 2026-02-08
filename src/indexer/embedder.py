"""ベクトル化"""

from openai import OpenAI

from src.config.settings import get_settings


class Embedder:
    """テキストをベクトル化"""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model

    def embed(self, text: str) -> list[float]:
        """単一テキストをベクトル化"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """複数テキストをバッチでベクトル化"""
        if not texts:
            return []

        # OpenAI APIは最大2048入力をサポート、バッチ処理
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)

        return all_embeddings
