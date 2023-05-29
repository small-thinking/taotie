"""Store the data in Notion.
"""
import asyncio
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

    async def save(
        self, data: List[Tuple[Dict[str, Any], Dict[str, Any]]], image_urls: List[str]
    ):
        """First create a database. And then create a page for each item in the database."""
        if not self.database_id:
            self.database_id = await self._get_or_create_database()
        for raw_item, processed_item in data:
            await self._add_to_database(
                self.database_id, raw_item, processed_item, image_urls
            )
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
                "Topics": {"multi_select": {}},
                "URL": {"url": {}},
            }
            response = await self.notion.databases.create(
                parent=parent,
                title=[{"type": "text", "text": {"content": "Taotie Knowledge Base"}}],
                properties=properties,
            )
            self.logger.info("Database created.")
            return response["id"]

    async def _add_to_database(
        self,
        database_id: str,
        item: Dict[str, Any],
        processed_item: Dict[str, Any],
        image_files: List[str],
    ) -> None:
        # Determine the icon.
        uri = item.get("uri", "")
        icon_emoji = "🔖"
        if uri.startswith("https://twitter.com"):
            icon_emoji = "🐦"
        elif uri.startswith("https://github.com"):
            icon_emoji = "💻"
        new_page = {
            "Title": [
                {
                    "type": "text",
                    "text": {"content": str(item["id"])},
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
            "Topics": [{"name": item} for item in processed_item.get("tags", [])],
            "URL": [
                {
                    "type": "text",
                    "text": {"content": item["uri"]},
                }
            ],
        }
        children = await self.create_page_blocks(item, processed_item, image_files)

        response = await self.notion.pages.create(
            parent={"type": "database_id", "database_id": database_id},
            properties=new_page,
            icon={"type": "emoji", "emoji": icon_emoji},
            children=children[:100],  # Can only add 100 blocks.
        )
        if "id" not in response:
            raise ValueError(f"Failed to add page to database: {response}")
        self.logger.info("Page added to database.")

    async def create_page_blocks(
        self,
        raw_info: Dict[str, Any],
        processed_info: Dict[str, Any],
        image_urls: List[str],
    ) -> List[Dict[str, Any]]:
        """Create the page blocks according to the information."""
        page_contents = []
        # Display the raw information as content.
        uri = raw_info.get("uri", "")
        reference_type = "bookmark"

        if uri.startswith("https://twitter.com"):
            reference_type = "embed"

        page_contents = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "Summary Images"},
                        }
                    ]
                },
            },
        ]
        # Upload the images if any.
        if image_urls:
            for image_url in image_urls:
                if image_url:
                    page_contents.append(
                        {
                            "object": "block",
                            "type": "image",
                            "image": {
                                "type": "external",
                                "external": {"url": image_url},
                            },
                        }
                    )

        page_contents.extend(
            [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": reference_type.capitalize()},
                            }
                        ]
                    },
                },
                {
                    "object": "block",
                    "type": reference_type,
                    reference_type: {"url": uri},
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": "Content"},
                            }
                        ]
                    },
                },
            ]
        )

        # Partition and put the content into blocks.
        content = raw_info.get("content", "")
        content = content.split("\n")
        for i, line in enumerate(content):
            if i >= 20:
                page_contents.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "Content too long. Truncated."},
                                }
                            ]
                        },
                    }
                )
                break
            page_contents.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": line},
                            }
                        ]
                    },
                }
            )
        return page_contents


async def run():
    raw_data = {
        "id": "123",
        "type": "test-type",
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": "This is a test long content." * 10,
        "uri": "https://github.com/taotie/taotie",
    }
    processed_data = {"summary": "This is a summary"}
    data = [(raw_data, processed_data)]
    notion = NotionStorage(
        root_page_id="987fd186553e4d2682e9a1de441a37ba", verbose=True
    )
    await notion.save(data, image_urls=["https://i.imgur.com/XXWcoH0.png"])


if __name__ == "__main__":
    asyncio.run(run())
