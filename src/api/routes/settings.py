"""設定エンドポイント"""

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

ENV_FILE_PATH = Path(__file__).parent.parent.parent.parent / ".env"


class SettingsRequest(BaseModel):
    """設定リクエスト"""

    notion_token: str | None = None
    notion_page_ids: str | None = None
    openai_api_key: str | None = None


class SettingsResponse(BaseModel):
    """設定レスポンス"""

    notion_token: str
    notion_page_ids: str
    openai_api_key: str
    notion_token_set: bool
    openai_api_key_set: bool


def _read_env_file() -> dict[str, str]:
    """環境変数ファイルを読み込む"""
    env_vars = {}
    if ENV_FILE_PATH.exists():
        for line in ENV_FILE_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def _write_env_file(env_vars: dict[str, str]) -> None:
    """環境変数ファイルを書き込む"""
    lines = [
        "# Notion API",
        f"NOTION_TOKEN={env_vars.get('NOTION_TOKEN', '')}",
        f"NOTION_DATABASE_IDS={env_vars.get('NOTION_DATABASE_IDS', '')}",
        f"NOTION_PAGE_IDS={env_vars.get('NOTION_PAGE_IDS', '')}",
        "",
        "# OpenAI API",
        f"OPENAI_API_KEY={env_vars.get('OPENAI_API_KEY', '')}",
        "",
        "# Optional",
        f"CHROMA_PERSIST_DIR={env_vars.get('CHROMA_PERSIST_DIR', './data/chroma')}",
        f"IMAGE_STORAGE_DIR={env_vars.get('IMAGE_STORAGE_DIR', './data/images')}",
    ]
    ENV_FILE_PATH.write_text("\n".join(lines) + "\n")


def _mask_secret(value: str) -> str:
    """シークレットをマスクする"""
    if not value or len(value) < 10:
        return "*" * len(value) if value else ""
    return value[:6] + "*" * (len(value) - 10) + value[-4:]


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """現在の設定を取得"""
    env_vars = _read_env_file()

    notion_token = env_vars.get("NOTION_TOKEN", "")
    openai_api_key = env_vars.get("OPENAI_API_KEY", "")

    return SettingsResponse(
        notion_token=_mask_secret(notion_token),
        notion_page_ids=env_vars.get("NOTION_PAGE_IDS", ""),
        openai_api_key=_mask_secret(openai_api_key),
        notion_token_set=bool(notion_token and notion_token != "secret_xxx"),
        openai_api_key_set=bool(openai_api_key and not openai_api_key.startswith("sk-xxx")),
    )


@router.post("", response_model=SettingsResponse)
async def update_settings(request: SettingsRequest) -> SettingsResponse:
    """設定を更新"""
    env_vars = _read_env_file()

    # 新しい値で更新（空でない場合のみ）
    if request.notion_token:
        env_vars["NOTION_TOKEN"] = request.notion_token
        os.environ["NOTION_TOKEN"] = request.notion_token

    if request.notion_page_ids is not None:
        env_vars["NOTION_PAGE_IDS"] = request.notion_page_ids
        os.environ["NOTION_PAGE_IDS"] = request.notion_page_ids

    if request.openai_api_key:
        env_vars["OPENAI_API_KEY"] = request.openai_api_key
        os.environ["OPENAI_API_KEY"] = request.openai_api_key

    # ファイルに書き込み
    _write_env_file(env_vars)

    # 設定キャッシュをクリア
    from src.config.settings import get_settings
    get_settings.cache_clear()

    notion_token = env_vars.get("NOTION_TOKEN", "")
    openai_api_key = env_vars.get("OPENAI_API_KEY", "")

    return SettingsResponse(
        notion_token=_mask_secret(notion_token),
        notion_page_ids=env_vars.get("NOTION_PAGE_IDS", ""),
        openai_api_key=_mask_secret(openai_api_key),
        notion_token_set=bool(notion_token and notion_token != "secret_xxx"),
        openai_api_key_set=bool(openai_api_key and not openai_api_key.startswith("sk-xxx")),
    )
