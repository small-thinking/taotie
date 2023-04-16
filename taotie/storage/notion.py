"""Store the data in Notion.
"""
import datetime
import os
from typing import Any, Dict, List, Optional, Tuple

from notion_client import AsyncClient

from taotie.storage.base import Storage


class NotionStorage(Storage):
    """Store the data into notion knowledge base."""

    def __init__(
        self,
        root_page_id: str,
        verbose: bool = False,
        **kwargs,
    ):
        Storage.__init__(self, verbose=verbose, **kwargs)
        self.token = os.environ.get("NOTION_TOKEN")
        if not self.token:
            raise ValueError("Please set the Notion token in .env.")
        self.notion = AsyncClient(auth=self.token)
        self.root_page_id = root_page_id
        self.database_id: Optional[str] = None
        self.logger.info("Notion storage initialized.")

    async def save(self, data: List[Tuple[Dict[str, Any], Dict[str, Any]]]):
        """First create a database. And then create a page for each item in the database."""
        if not self.database_id:
            self.database_id = await self._get_or_create_database()
        for raw_item, processed_item in data:
            await self._add_to_database(self.database_id, raw_item, processed_item)
        self.logger.info("Notion storage saved.")

    async def _get_or_create_database(self) -> str:
        """Get the database id or create a new one if it does not exist."""
        results = await self.notion.search(
            query=self.root_page_id, filter={"property": "object", "value": "database"}
        )
        results = results.get("results")
        if len(results):
            database_id = results[0]["id"]
            self.logger.info(f"Database {database_id} already exists.")
            return results[0]["id"]
        else:
            # Create a new database.
            parent = {"page_id": self.root_page_id}
            properties: Dict[str, Any] = {
                "Title": {"title": {}},
                "Type": {"select": {}},
                "Created Time": {"date": {}},
                "Summary": {"rich_text": {}},
            }
            response = await self.notion.databases.create(
                parent=parent,
                title=[{"type": "text", "text": {"content": "Taotie Knowledge Base"}}],
                properties=properties,
            )
            self.logger.info("Database created.")
            return response["id"]

    async def _add_to_database(
        self, database_id: str, item: Dict[str, Any], processed_item: Dict[str, Any]
    ) -> None:
        self.logger.info("Adding page to database...")
        new_page = {
            "Title": [
                {
                    "type": "text",
                    "text": {"content": item["id"]},
                }
            ],
            "Created Time": {"start": item["datetime"]},
            "Type": {"name": item["type"]},
            "Summary": [
                {
                    "type": "text",
                    "text": {"content": processed_item.get("summary", "N/A")},
                }
            ],
        }
        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": item.get("content", "N/A")},
                        }
                    ]
                },
            }
        ]

        await self.notion.pages.create(
            parent={"type": "database_id", "database_id": database_id},
            properties=new_page,
            children=children,
        )
        self.logger.info("Page added to database.")


async def run():
    raw_data = {
        "id": "123",
        "type": "test-type",
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": "This is a test long content." * 10,
    }
    processed_data = {"summary": "This is a summary"}
    data = [(raw_data, processed_data)]
    notion = NotionStorage(
        root_page_id="987fd186553e4d2682e9a1de441a37ba", verbose=True
    )
    await notion.save(data)
