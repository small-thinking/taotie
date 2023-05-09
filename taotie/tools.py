"""
"""
import asyncio
import os

from taotie.reporter.notion_reporter import NotionReporter
from taotie.utils import *


async def run_notion_reporter():
    """Run the script to generate the notion report."""
    load_dotenv()
    database_id = os.environ.get("NOTION_DATABASE_ID")
    tags = os.environ.get("CANDIDATE_TAGS", "").split(",")
    reporter = NotionReporter(
        knowledge_source_uri=database_id,
        date_lookback=2,
        type_filter="github-repo",
        topic_filters=tags,
        model_type="gpt-4",
    )
    await reporter.distill()


if __name__ == "__main__":
    asyncio.run(run_notion_reporter())
