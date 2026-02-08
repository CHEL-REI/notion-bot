"""アプリケーション設定管理"""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Notion API
    notion_token: str
    notion_database_ids: str = ""  # カンマ区切り（オプション）
    notion_page_ids: str = ""  # カンマ区切り（オプション）

    # OpenAI API
    openai_api_key: str

    # Storage paths
    chroma_persist_dir: Path = Path("./data/chroma")
    image_storage_dir: Path = Path("./data/images")

    # Model settings
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o"

    # Chunking settings
    chunk_size: int = 1000
    chunk_overlap: int = 200

    @property
    def database_id_list(self) -> list[str]:
        """データベースIDのリストを返す"""
        return [db_id.strip() for db_id in self.notion_database_ids.split(",") if db_id.strip()]

    @property
    def page_id_list(self) -> list[str]:
        """ページIDのリストを返す"""
        return [page_id.strip() for page_id in self.notion_page_ids.split(",") if page_id.strip()]


@lru_cache
def get_settings() -> Settings:
    """設定のシングルトンインスタンスを返す"""
    return Settings()
