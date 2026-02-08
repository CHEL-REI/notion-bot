"""チャンク化ロジック"""

from dataclasses import dataclass, field

from src.config.settings import get_settings
from src.notion.models import BlockType, NotionBlock, NotionPage


@dataclass
class Chunk:
    """テキストチャンク"""

    id: str
    text: str
    page_id: str
    page_title: str
    page_url: str
    image_paths: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Chunker:
    """Notionページをチャンクに分割"""

    HEADING_TYPES = {BlockType.HEADING_1, BlockType.HEADING_2, BlockType.HEADING_3}

    def __init__(self):
        settings = get_settings()
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap

    def chunk_page(self, page: NotionPage) -> list[Chunk]:
        """ページをチャンクに分割"""
        # まずブロックをセクションに分割
        sections = self._split_into_sections(page.blocks)

        # 各セクションをチャンクに変換
        chunks = []
        for i, section in enumerate(sections):
            section_chunks = self._create_chunks_from_section(
                section=section,
                page=page,
                section_index=i,
            )
            chunks.extend(section_chunks)

        return chunks

    def _split_into_sections(self, blocks: list[NotionBlock]) -> list[list[NotionBlock]]:
        """ブロックをHeadingをセクション境界として分割"""
        sections = []
        current_section = []

        def process_blocks(blocks: list[NotionBlock]):
            nonlocal current_section

            for block in blocks:
                if block.type in self.HEADING_TYPES:
                    # 現在のセクションを保存して新しいセクションを開始
                    if current_section:
                        sections.append(current_section)
                    current_section = [block]
                else:
                    current_section.append(block)

                # 子ブロックも処理（ただしHeadingの場合は新セクションとして扱わない）
                if block.children:
                    for child in block.children:
                        if child.type not in self.HEADING_TYPES:
                            current_section.append(child)
                        else:
                            process_blocks([child])

        process_blocks(blocks)

        # 最後のセクションを追加
        if current_section:
            sections.append(current_section)

        return sections

    def _create_chunks_from_section(
        self,
        section: list[NotionBlock],
        page: NotionPage,
        section_index: int,
    ) -> list[Chunk]:
        """セクションからチャンクを作成"""
        chunks = []
        current_text = ""
        current_images = []
        chunk_index = 0

        for block in section:
            block_text = self._get_block_text(block)
            block_images = self._get_block_images(block)

            # 画像がある場合は、画像の前後のテキストと一緒にチャンクを作成
            if block_images:
                # 現在のテキストと画像を合わせてチャンクを作成
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
                # テキストのみの場合はサイズチェック
                new_text = current_text + "\n" + block_text if current_text else block_text

                if len(new_text) > self.chunk_size:
                    # 現在のチャンクを保存
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

                    # オーバーラップを考慮して新しいチャンクを開始
                    if self.chunk_overlap > 0 and current_text:
                        overlap_text = current_text[-self.chunk_overlap :]
                        current_text = overlap_text + "\n" + block_text
                    else:
                        current_text = block_text
                    current_images = []
                else:
                    current_text = new_text

        # 残りのテキストをチャンクとして追加
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
        """ブロックからテキストを取得"""
        text_parts = []

        # ブロックタイプに応じたプレフィックス
        prefix_map = {
            BlockType.HEADING_1: "# ",
            BlockType.HEADING_2: "## ",
            BlockType.HEADING_3: "### ",
            BlockType.BULLETED_LIST_ITEM: "• ",
            BlockType.NUMBERED_LIST_ITEM: "1. ",
            BlockType.QUOTE: "> ",
            BlockType.CODE: "```\n",
        }

        suffix_map = {
            BlockType.CODE: "\n```",
        }

        prefix = prefix_map.get(block.type, "")
        suffix = suffix_map.get(block.type, "")

        if block.text:
            text_parts.append(f"{prefix}{block.text}{suffix}")

        # 画像の説明文もテキストとして追加
        if block.image and block.image.description:
            text_parts.append(f"[画像説明: {block.image.description}]")

        return "\n".join(text_parts)

    def _get_block_images(self, block: NotionBlock) -> list[str]:
        """ブロックから画像パスを取得"""
        images = []
        if block.image and block.image.local_path:
            images.append(block.image.local_path)
        return images
