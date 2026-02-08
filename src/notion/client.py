"""Notion APIクライアント"""

from notion_client import Client

from src.config.settings import get_settings


class NotionClient:
    """Notion API操作用クライアント"""

    def __init__(self):
        settings = get_settings()
        self.client = Client(auth=settings.notion_token)
        self.database_ids = settings.database_id_list
        self.page_ids = settings.page_id_list

    def get_database_pages(self, database_id: str) -> list[dict]:
        """データベース内のすべてのページを取得"""
        pages = []
        cursor = None

        while True:
            response = self.client.databases.query(
                database_id=database_id,
                start_cursor=cursor,
            )
            pages.extend(response["results"])

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return pages

    def get_page(self, page_id: str) -> dict:
        """ページ情報を取得"""
        return self.client.pages.retrieve(page_id=page_id)

    def get_page_blocks(self, page_id: str) -> list[dict]:
        """ページ内のすべてのブロックを取得（再帰的）"""
        return self._get_blocks_recursive(page_id)

    def _get_blocks_recursive(self, block_id: str) -> list[dict]:
        """ブロックを再帰的に取得"""
        blocks = []
        cursor = None

        while True:
            response = self.client.blocks.children.list(
                block_id=block_id,
                start_cursor=cursor,
            )

            for block in response["results"]:
                if block.get("has_children"):
                    block["children"] = self._get_blocks_recursive(block["id"])
                blocks.append(block)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return blocks

    def get_all_pages(self) -> list[dict]:
        """すべての設定済みデータベース・ページからページを取得"""
        all_pages = []

        # データベースからページを取得
        for db_id in self.database_ids:
            pages = self.get_database_pages(db_id)
            all_pages.extend(pages)

        # 直接指定されたページを取得
        for page_id in self.page_ids:
            page = self.get_page(page_id)
            all_pages.append(page)

        return all_pages
