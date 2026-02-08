"""RAGチェーン"""

from dataclasses import dataclass

from openai import OpenAI

from src.config.settings import get_settings
from src.rag.prompts import RAG_PROMPT_TEMPLATE, SYSTEM_PROMPT, format_context
from src.rag.retriever import Retriever


@dataclass
class ChatResponse:
    """チャット応答"""

    answer: str
    sources: list[dict]
    image_paths: list[str]


class RAGChain:
    """RAGベースの回答生成チェーン"""

    def __init__(self, top_k: int = 5):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
        self.retriever = Retriever(top_k=top_k)

    def chat(self, question: str) -> ChatResponse:
        """質問に対してRAGベースで回答を生成"""
        # 関連ドキュメントを検索
        search_results = self.retriever.retrieve(question)

        if not search_results:
            return ChatResponse(
                answer="申し訳ありませんが、この質問に関連する情報がドキュメントに見つかりませんでした。",
                sources=[],
                image_paths=[],
            )

        # コンテキストを構築
        context = format_context(search_results)

        # プロンプトを構築
        user_prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        # LLMで回答を生成
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        answer = response.choices[0].message.content or ""

        # 画像パスを収集
        all_image_paths = []
        for result in search_results:
            all_image_paths.extend(result.get("image_paths", []))

        # ソース情報を整理
        sources = [
            {
                "page_title": r["page_title"],
                "page_url": r["page_url"],
                "score": r["score"],
            }
            for r in search_results
        ]

        return ChatResponse(
            answer=answer,
            sources=sources,
            image_paths=list(set(all_image_paths)),  # 重複を除去
        )

    def chat_with_history(
        self, question: str, history: list[dict]
    ) -> ChatResponse:
        """会話履歴を考慮してRAGベースで回答を生成"""
        # 関連ドキュメントを検索
        search_results = self.retriever.retrieve(question)

        # コンテキストを構築
        context = format_context(search_results) if search_results else "関連情報が見つかりませんでした。"

        # プロンプトを構築
        user_prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        # メッセージ履歴を構築
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 過去の会話を追加
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        # 現在の質問を追加
        messages.append({"role": "user", "content": user_prompt})

        # LLMで回答を生成
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )

        answer = response.choices[0].message.content or ""

        # 画像パスを収集
        all_image_paths = []
        for result in search_results:
            all_image_paths.extend(result.get("image_paths", []))

        # ソース情報を整理
        sources = [
            {
                "page_title": r["page_title"],
                "page_url": r["page_url"],
                "score": r["score"],
            }
            for r in search_results
        ]

        return ChatResponse(
            answer=answer,
            sources=sources,
            image_paths=list(set(all_image_paths)),
        )
