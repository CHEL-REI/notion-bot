"""Notionデータモデル"""

from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    """Notionブロックタイプ"""

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
    BOOKMARK = "bookmark"
    EMBED = "embed"
    VIDEO = "video"
    FILE = "file"
    PDF = "pdf"
    UNKNOWN = "unknown"


@dataclass
class ImageInfo:
    """画像情報"""

    url: str
    local_path: str | None = None
    description: str | None = None
    caption: str | None = None


@dataclass
class NotionBlock:
    """Notionブロック"""

    id: str
    type: BlockType
    text: str = ""
    image: ImageInfo | None = None
    children: list["NotionBlock"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class NotionPage:
    """Notionページ"""

    id: str
    title: str
    url: str
    blocks: list[NotionBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def images(self) -> list[ImageInfo]:
        """ページ内のすべての画像を取得"""

        def collect_images(blocks: list[NotionBlock]) -> list[ImageInfo]:
            images = []
            for block in blocks:
                if block.image:
                    images.append(block.image)
                images.extend(collect_images(block.children))
            return images

        return collect_images(self.blocks)
