"""Notionページローダー"""

from src.notion.client import NotionClient
from src.notion.models import BlockType, ImageInfo, NotionBlock, NotionPage


class NotionLoader:
    """Notionページをパースしてデータモデルに変換"""

    def __init__(self):
        self.client = NotionClient()

    def load_all_pages(self) -> list[NotionPage]:
        """すべてのページを読み込む"""
        raw_pages = self.client.get_all_pages()
        pages = []

        for raw_page in raw_pages:
            page = self.load_page(raw_page["id"])
            pages.append(page)

        return pages

    def load_page(self, page_id: str) -> NotionPage:
        """単一ページを読み込む"""
        raw_page = self.client.get_page(page_id)
        raw_blocks = self.client.get_page_blocks(page_id)

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

    def _extract_title(self, page: dict) -> str:
        """ページタイトルを抽出"""
        properties = page.get("properties", {})

        # Titleプロパティを探す（データベースページ）
        for prop in properties.values():
            if prop.get("type") == "title":
                title_items = prop.get("title", [])
                title = "".join(item.get("plain_text", "") for item in title_items)
                if title:
                    return title

        # スタンドアロンページの場合（titleプロパティ直下）
        if "title" in properties:
            title_prop = properties["title"]
            if isinstance(title_prop, dict) and "title" in title_prop:
                title_items = title_prop.get("title", [])
                title = "".join(item.get("plain_text", "") for item in title_items)
                if title:
                    return title

        # URLからタイトルを推測（フォールバック）
        url = page.get("url", "")
        if url:
            # URLの最後の部分からタイトルを抽出（例: UX-d1f5824fe696469095ca8340641ba8ce）
            parts = url.rstrip("/").split("/")[-1].split("-")
            if len(parts) > 1:
                # 最後のIDを除いた部分をタイトルとして使用
                return "-".join(parts[:-1])

        return "Untitled"

    def _parse_block(self, block: dict) -> NotionBlock:
        """ブロックをパース"""
        block_id = block.get("id", "")
        block_type_str = block.get("type", "unknown")

        try:
            block_type = BlockType(block_type_str)
        except ValueError:
            block_type = BlockType.UNKNOWN

        text = ""
        image = None
        metadata = {}

        # ブロックタイプに応じたテキスト抽出
        block_content = block.get(block_type_str, {})

        if block_type == BlockType.IMAGE:
            image = self._extract_image(block_content)
        elif block_type == BlockType.CODE:
            text = self._extract_rich_text(block_content.get("rich_text", []))
            metadata["language"] = block_content.get("language", "")
        elif block_type in (BlockType.TABLE, BlockType.TABLE_ROW):
            text = self._extract_table_text(block, block_type)
        else:
            text = self._extract_rich_text(block_content.get("rich_text", []))

        # 子ブロックをパース
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
        """リッチテキストからプレーンテキストを抽出"""
        return "".join(item.get("plain_text", "") for item in rich_text)

    def _extract_image(self, content: dict) -> ImageInfo:
        """画像情報を抽出"""
        image_type = content.get("type", "")

        if image_type == "external":
            url = content.get("external", {}).get("url", "")
        elif image_type == "file":
            url = content.get("file", {}).get("url", "")
        else:
            url = ""

        caption = self._extract_rich_text(content.get("caption", []))

        return ImageInfo(url=url, caption=caption)

    def _extract_table_text(self, block: dict, block_type: BlockType) -> str:
        """テーブルからテキストを抽出"""
        if block_type == BlockType.TABLE:
            # テーブルの場合は子要素（行）から構築
            rows = []
            for child in block.get("children", []):
                if child.get("type") == "table_row":
                    cells = child.get("table_row", {}).get("cells", [])
                    row_text = " | ".join(
                        self._extract_rich_text(cell) for cell in cells
                    )
                    rows.append(row_text)
            return "\n".join(rows)
        elif block_type == BlockType.TABLE_ROW:
            cells = block.get("table_row", {}).get("cells", [])
            return " | ".join(self._extract_rich_text(cell) for cell in cells)
        return ""
