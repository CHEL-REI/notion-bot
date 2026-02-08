"""チャットエンドポイント"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.rag.chain import RAGChain

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """チャットリクエスト"""

    message: str
    history: list[dict] = []


class ChatResponseModel(BaseModel):
    """チャットレスポンス"""

    answer: str
    sources: list[dict]
    image_paths: list[str]


@router.post("", response_model=ChatResponseModel)
async def chat(request: ChatRequest) -> ChatResponseModel:
    """質問に対してRAGベースで回答を生成"""
    chain = RAGChain()

    if request.history:
        response = chain.chat_with_history(request.message, request.history)
    else:
        response = chain.chat(request.message)

    return ChatResponseModel(
        answer=response.answer,
        sources=response.sources,
        image_paths=response.image_paths,
    )
