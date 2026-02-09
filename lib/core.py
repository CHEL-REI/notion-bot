"""ビジネスロジック: データモデル、NotionLoader、ImageProcessor、Chunker、VectorStore、RAGChain"""

import hashlib
import json
import mimetypes
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import httpx
import streamlit as st
from openai import OpenAI
import chromadb
from chromadb.config import Settings as ChromaSettings
from notion_client import Client as NotionClient


# ==================== データモデル ====================

class BlockType(Enum):
    PARAGRAPH = "paragraph"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    TOGGLE = "toggle"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    IMAGE = "image"
    DIVIDER = "divider"
    TABLE = "table"
    TABLE_ROW = "table_row"
    CHILD_PAGE = "child_page"
    CHILD_DATABASE = "child_database"
    UNKNOWN = "unknown"


@dataclass
class ImageInfo:
    url: str
    local_path: str | None = None
    description: str | None = None
    caption: str | None = None


@dataclass
class NotionBlock:
    id: str
    type: BlockType
    text: str = ""
    image: ImageInfo | None = None
    children: list["NotionBlock"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class NotionPage:
    id: str
    title: str
    url: str
    blocks: list[NotionBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def images(self) -> list[ImageInfo]:
        def collect_images(blocks: list[NotionBlock]) -> list[ImageInfo]:
            images = []
            for block in blocks:
                if block.image:
                    images.append(block.image)
                images.extend(collect_images(block.children))
            return images
        return collect_images(self.blocks)


@dataclass
class Chunk:
    id: str
    text: str
    page_id: str
    page_title: str
    page_url: str
    image_paths: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ==================== 設定管理 ====================

_CONFIG_FILE = Path("/tmp/notion_bot_config.json")


def _load_config() -> dict:
    """永続化設定ファイルを読み込む。"""
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(config: dict) -> None:
    """永続化設定ファイルに書き込む。"""
    _CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")


def save_page_ids(page_ids: str) -> None:
    """NotionページIDを永続保存する。"""
    config = _load_config()
    config["notion_page_ids"] = page_ids
    _save_config(config)


def load_page_ids() -> str | None:
    """保存済みページIDを読み込む。"""
    return _load_config().get("notion_page_ids")


def save_notion_token(token: str) -> None:
    """Notion Integration Tokenを永続保存する。"""
    config = _load_config()
    config["notion_token"] = token
    _save_config(config)


def load_notion_token() -> str | None:
    """保存済みNotion Tokenを読み込む。"""
    return _load_config().get("notion_token")


def save_last_sync_time() -> None:
    """最終同期時刻を記録する。"""
    config = _load_config()
    config["last_sync_time"] = datetime.now(timezone.utc).isoformat()
    _save_config(config)


def needs_resync(interval_hours: float = 1.0) -> bool:
    """前回同期から指定時間が経過していればTrueを返す。"""
    config = _load_config()
    last_sync = config.get("last_sync_time")
    if not last_sync:
        return True
    try:
        last_dt = datetime.fromisoformat(last_sync)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        return elapsed > interval_hours * 3600
    except (ValueError, TypeError):
        return True


def get_settings():
    """Streamlit secretsまたはsession_stateから設定を取得"""
    settings = {}

    try:
        settings['notion_token'] = st.secrets.get('NOTION_TOKEN', '')
        settings['openai_api_key'] = st.secrets.get('OPENAI_API_KEY', '')
        settings['notion_page_ids'] = st.secrets.get('NOTION_PAGE_IDS', '')
    except Exception:
        pass

    # ファイル永続化を優先
    saved_token = load_notion_token()
    if saved_token:
        settings['notion_token'] = saved_token
    saved_page_ids = load_page_ids()
    if saved_page_ids:
        settings['notion_page_ids'] = saved_page_ids

    if 'notion_token' in st.session_state and st.session_state.notion_token:
        settings['notion_token'] = st.session_state.notion_token
    if 'openai_api_key' in st.session_state and st.session_state.openai_api_key:
        settings['openai_api_key'] = st.session_state.openai_api_key

    return settings


# ==================== Notionローダー ====================

class NotionLoader:
    def __init__(self, token: str, page_ids: list[str]):
        self.client = NotionClient(auth=token)
        self.page_ids = page_ids

    def load_all_pages(self) -> list[NotionPage]:
        pages = []
        for page_id in self.page_ids:
            if page_id.strip():
                page = self.load_page(page_id.strip())
                pages.append(page)
        return pages

    def load_page(self, page_id: str) -> NotionPage:
        raw_page = self.client.pages.retrieve(page_id=page_id)
        raw_blocks = self._get_blocks_recursive(page_id)
        title = self._extract_title(raw_page)
        url = raw_page.get("url", "")
        blocks = [self._parse_block(b) for b in raw_blocks]
        return NotionPage(
            id=page_id,
            title=title,
            url=url,
            blocks=blocks,
            metadata={
                "created_time": raw_page.get("created_time"),
                "last_edited_time": raw_page.get("last_edited_time"),
            },
        )

    def _get_blocks_recursive(self, block_id: str) -> list[dict]:
        blocks = []
        cursor = None
        while True:
            response = self.client.blocks.children.list(block_id=block_id, start_cursor=cursor)
            for block in response["results"]:
                if block.get("has_children"):
                    block["children"] = self._get_blocks_recursive(block["id"])
                blocks.append(block)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return blocks

    def _extract_title(self, page: dict) -> str:
        properties = page.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "title":
                title_items = prop.get("title", [])
                title = "".join(item.get("plain_text", "") for item in title_items)
                if title:
                    return title
        url = page.get("url", "")
        if url:
            parts = url.rstrip("/").split("/")[-1].split("-")
            if len(parts) > 1:
                return "-".join(parts[:-1])
        return "Untitled"

    def _parse_block(self, block: dict) -> NotionBlock:
        block_id = block.get("id", "")
        block_type_str = block.get("type", "unknown")
        try:
            block_type = BlockType(block_type_str)
        except ValueError:
            block_type = BlockType.UNKNOWN
        text = ""
        image = None
        metadata = {}
        block_content = block.get(block_type_str, {})
        if block_type == BlockType.IMAGE:
            image = self._extract_image(block_content)
        elif block_type == BlockType.CODE:
            text = self._extract_rich_text(block_content.get("rich_text", []))
            metadata["language"] = block_content.get("language", "")
        else:
            text = self._extract_rich_text(block_content.get("rich_text", []))
        children = []
        if "children" in block:
            children = [self._parse_block(child) for child in block["children"]]
        return NotionBlock(
            id=block_id,
            type=block_type,
            text=text,
            image=image,
            children=children,
            metadata=metadata,
        )

    def _extract_rich_text(self, rich_text: list) -> str:
        return "".join(item.get("plain_text", "") for item in rich_text)

    def _extract_image(self, content: dict) -> ImageInfo:
        image_type = content.get("type", "")
        if image_type == "external":
            url = content.get("external", {}).get("url", "")
        elif image_type == "file":
            url = content.get("file", {}).get("url", "")
        else:
            url = ""
        caption = self._extract_rich_text(content.get("caption", []))
        return ImageInfo(url=url, caption=caption)


# ==================== 画像処理 ====================

class ImageProcessor:
    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.storage_dir = Path("/tmp/notion_images")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def process_image(self, image: ImageInfo) -> ImageInfo:
        if not image.url:
            return image
        local_path = self._download_image(image.url)
        if not local_path:
            return image
        image.local_path = str(local_path)
        description = self._generate_description(local_path, image.caption)
        image.description = description
        return image

    def _download_image(self, url: str) -> Path | None:
        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "image/png")
                ext = mimetypes.guess_extension(content_type.split(";")[0]) or ".png"
                filename = f"{url_hash}{ext}"
                local_path = self.storage_dir / filename
                local_path.write_bytes(response.content)
                return local_path
        except Exception as e:
            st.warning(f"画像ダウンロードエラー: {e}")
            return None

    def _generate_description(self, image_path: Path, caption: str | None) -> str:
        try:
            image_data = image_path.read_bytes()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(str(image_path))
            mime_type = mime_type or "image/png"
            prompt = "この画像の内容を日本語で詳しく説明してください。"
            if caption:
                prompt += f"\n\nキャプション: {caption}"
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}", "detail": "high"}},
                    ],
                }],
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            st.warning(f"画像説明生成エラー: {e}")
            return caption or ""


# ==================== チャンカー ====================

class Chunker:
    HEADING_TYPES = {BlockType.HEADING_1, BlockType.HEADING_2, BlockType.HEADING_3}

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_page(self, page: NotionPage) -> list[Chunk]:
        sections = self._split_into_sections(page.blocks)
        chunks = []
        for i, section in enumerate(sections):
            section_chunks = self._create_chunks_from_section(section, page, i)
            chunks.extend(section_chunks)
        return chunks

    def _split_into_sections(self, blocks: list[NotionBlock]) -> list[list[NotionBlock]]:
        sections = []
        current_section = []

        def process_blocks(blocks: list[NotionBlock]):
            nonlocal current_section
            for block in blocks:
                if block.type in self.HEADING_TYPES:
                    if current_section:
                        sections.append(current_section)
                    current_section = [block]
                else:
                    current_section.append(block)
                if block.children:
                    for child in block.children:
                        if child.type not in self.HEADING_TYPES:
                            current_section.append(child)
                        else:
                            process_blocks([child])

        process_blocks(blocks)
        if current_section:
            sections.append(current_section)
        return sections

    def _create_chunks_from_section(self, section: list[NotionBlock], page: NotionPage, section_index: int) -> list[Chunk]:
        chunks = []
        current_text = ""
        current_images = []
        chunk_index = 0

        for block in section:
            block_text = self._get_block_text(block)
            block_images = self._get_block_images(block)

            if block_images:
                combined_text = current_text + "\n" + block_text if current_text else block_text
                combined_images = current_images + block_images
                if combined_text.strip() or combined_images:
                    chunk = Chunk(
                        id=f"{page.id}_{section_index}_{chunk_index}",
                        text=combined_text.strip(),
                        page_id=page.id,
                        page_title=page.title,
                        page_url=page.url,
                        image_paths=combined_images,
                        metadata={"section_index": section_index},
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                current_text = ""
                current_images = []
            else:
                new_text = current_text + "\n" + block_text if current_text else block_text
                if len(new_text) > self.chunk_size:
                    if current_text.strip():
                        chunk = Chunk(
                            id=f"{page.id}_{section_index}_{chunk_index}",
                            text=current_text.strip(),
                            page_id=page.id,
                            page_title=page.title,
                            page_url=page.url,
                            image_paths=current_images.copy(),
                            metadata={"section_index": section_index},
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                    if self.chunk_overlap > 0 and current_text:
                        overlap_text = current_text[-self.chunk_overlap:]
                        current_text = overlap_text + "\n" + block_text
                    else:
                        current_text = block_text
                    current_images = []
                else:
                    current_text = new_text

        if current_text.strip():
            chunk = Chunk(
                id=f"{page.id}_{section_index}_{chunk_index}",
                text=current_text.strip(),
                page_id=page.id,
                page_title=page.title,
                page_url=page.url,
                image_paths=current_images,
                metadata={"section_index": section_index},
            )
            chunks.append(chunk)
        return chunks

    def _get_block_text(self, block: NotionBlock) -> str:
        text_parts = []
        prefix_map = {
            BlockType.HEADING_1: "# ",
            BlockType.HEADING_2: "## ",
            BlockType.HEADING_3: "### ",
            BlockType.BULLETED_LIST_ITEM: "• ",
            BlockType.NUMBERED_LIST_ITEM: "1. ",
            BlockType.QUOTE: "> ",
            BlockType.CODE: "```\n",
        }
        suffix_map = {BlockType.CODE: "\n```"}
        prefix = prefix_map.get(block.type, "")
        suffix = suffix_map.get(block.type, "")
        if block.text:
            text_parts.append(f"{prefix}{block.text}{suffix}")
        if block.image and block.image.description:
            text_parts.append(f"[画像説明: {block.image.description}]")
        return "\n".join(text_parts)

    def _get_block_images(self, block: NotionBlock) -> list[str]:
        images = []
        if block.image and block.image.local_path:
            images.append(block.image.local_path)
        return images


# ==================== ベクトルストア ====================

class VectorStore:
    COLLECTION_NAME = "notion_pages"
    PERSIST_DIR = "/tmp/notion_bot_chroma"

    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.client = chromadb.PersistentClient(
            path=self.PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def embed(self, text: str) -> list[float]:
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)
        return all_embeddings

    def add_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embed_batch(texts)
        ids = [chunk.id for chunk in chunks]
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
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_embedding = self.embed(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        search_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                image_paths = json.loads(metadata.get("image_paths", "[]"))
                search_results.append({
                    "text": doc,
                    "page_id": metadata.get("page_id", ""),
                    "page_title": metadata.get("page_title", ""),
                    "page_url": metadata.get("page_url", ""),
                    "image_paths": image_paths,
                    "score": 1 - distance,
                })
        return search_results

    def clear(self) -> None:
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def get_stats(self) -> dict:
        return {"total_chunks": self.collection.count()}


# ==================== RAGチェーン ====================

SYSTEM_PROMPT = """あなたは社内ドキュメント（Notion）に基づいて質問に答えるアシスタントです。

以下のルールに従って回答してください：

1. 回答は必ず提供されたコンテキストに基づいてください。情報がない場合は正直に伝えてください。
2. 出典となるページタイトルを回答の最後に記載してください。
3. 簡潔で明確に回答してください。
4. 日本語で回答してください。
"""

RAG_PROMPT_TEMPLATE = """以下はNotionドキュメントから取得した関連情報です：

---
{context}
---

上記の情報を参考に、以下の質問に答えてください：

質問: {question}
"""


def format_context(search_results: list[dict]) -> str:
    context_parts = []
    for i, result in enumerate(search_results, 1):
        part = f"### 情報 {i} (ページ: {result['page_title']})\n"
        part += f"{result['text']}\n"
        context_parts.append(part)
    return "\n---\n".join(context_parts)


class RAGChain:
    def __init__(self, openai_api_key: str, vector_store: VectorStore):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.vector_store = vector_store

    def chat(self, question: str) -> dict:
        search_results = self.vector_store.search(question, top_k=5)
        if not search_results:
            return {
                "answer": "申し訳ありませんが、この質問に関連する情報がドキュメントに見つかりませんでした。",
                "sources": [],
                "image_paths": [],
            }
        context = format_context(search_results)
        user_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        answer = response.choices[0].message.content or ""
        all_image_paths = []
        for result in search_results:
            all_image_paths.extend(result.get("image_paths", []))
        sources = [
            {"page_title": r["page_title"], "page_url": r["page_url"], "score": r["score"]}
            for r in search_results
        ]
        return {
            "answer": answer,
            "sources": sources,
            "image_paths": list(set(all_image_paths)),
        }


# ==================== ユーティリティ ====================

def extract_page_id_from_url(url: str) -> str:
    url = url.strip().rstrip("/")
    last_part = url.split("/")[-1]
    if "-" in last_part:
        potential_id = last_part.split("-")[-1]
        if len(potential_id) == 32:
            return potential_id
    if len(last_part) == 32:
        return last_part
    return url


def display_image(img_path: str):
    local_path = Path(img_path)
    if local_path.exists():
        st.image(str(local_path), use_container_width=True)


def run_sync(settings: dict) -> VectorStore:
    """Notionデータを同期してVectorStoreを返す。"""
    raw = settings['notion_page_ids'].replace(",", "\n")
    page_ids = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line:
            page_id = extract_page_id_from_url(line)
            if page_id:
                page_ids.append(page_id)

    loader = NotionLoader(settings['notion_token'], page_ids)
    pages = loader.load_all_pages()
    st.info(f"{len(pages)}ページを取得")

    image_processor = ImageProcessor(settings['openai_api_key'])
    for page in pages:
        for image in page.images:
            image_processor.process_image(image)

    chunker = Chunker()
    all_chunks = []
    for page in pages:
        chunks = chunker.chunk_page(page)
        all_chunks.extend(chunks)

    vector_store = VectorStore(settings['openai_api_key'])
    vector_store.clear()
    vector_store.add_chunks(all_chunks)

    save_last_sync_time()
    st.success(f"同期完了: {len(all_chunks)}チャンク")
    return vector_store
