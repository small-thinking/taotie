"""Notion reporter will check the gathered knowledge in notion and generate the text report for the AI related contents.
"""
import asyncio
import json
import os
from datetime import date, datetime, timedelta
from typing import Dict, List

import openai
import pytz  # type: ignore
from notion_client import AsyncClient

from taotie.reporter.base_reporter import BaseReporter
from taotie.utils import *


class NotionReporter(BaseReporter):
    """NotionReporter will check the gathered knowledge in notion and
    generate the text report accordingly."""

    def __init__(
        self,
        knowledge_source_uri: str,
        date_lookback: int,
        type_filter: str,
        topic_filters: List[str],
        verbose: bool = False,
        **kwargs,
    ):
        """
        Args:
            knowledge_source_uri: The uri of the notion database id.
        """
        super().__init__(knowledge_source_uri=knowledge_source_uri, verbose=verbose)
        self.token = os.environ.get("NOTION_TOKEN")
        if not self.token:
            raise ValueError("Please set the Notion token in .env.")
        self.date_lookback = max(0, date_lookback)
        self.type_filter = type_filter
        self.topic_filters = topic_filters
        # Model configs.
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("Please set OPENAI_API_KEY in .env.")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.model_type = kwargs.get("model_type", "gpt-3.5-turbo")
        # Prompt.
        language = kwargs.get("language", "Chinese")
        self.report_prompt = f"""
        Please generate a report that will be published by the Wechat blog based on the json string in the triple quotes.
        Please follow the following rules STRICTLY:
        1. Please summarize in {language}.
        2. Please given a short overall summary of the article that is about a report of the advances of AI.
        3. Please generate each item as an individual section, include the URL in each of the item, and \
            including the strength of recommendation (draw 1-5 stars) and the reason to recommend. \
            Please make the summary as informative as possible.
        4. Please generate the description in an attractive way, so that the readers will be willing to check the content.
        5. Rank and only keep at most the top 10 items based on the recommendation strength.

        """

    async def _connect(self):
        self.notion = AsyncClient(auth=self.token)

    async def _cleanup(self):
        print("cleanup")

    async def _distill(self):
        """Grab the gathered knowledge from notion database and generate the text report.

        Returns:
            str: The text report.
        """
        doc_list = await self._retrieve_data()
        self.logger.output(f"Number docs retrieved: {len(doc_list)}\n")
        report = await self._generate_report(doc_list)
        self.logger.output(f"{report}\n", color=Fore.BLUE)

    async def _retrieve_data(self) -> List[Dict[str, Any]]:
        # Get the date range.
        timezone = pytz.timezone("America/Los_Angeles")
        start_date = datetime.now(timezone) - timedelta(days=self.date_lookback)
        date_start = start_date.astimezone(timezone).isoformat()
        # Query the database and convert them into json if not.
        filter_params = {
            "and": [
                {
                    "property": "Created Time",
                    "date": {
                        "after": date_start,
                    },
                },
                {"property": "Type", "select": {"equals": self.type_filter}},
                {"or": []},
            ]
        }
        # # Add tag filters.
        if self.topic_filters:
            and_blob: List[Any] = filter_params["and"]
            for topic in self.topic_filters:
                and_blob[-1]["or"].append(
                    {
                        "property": "Topics",
                        "multi_select": {"contains": topic},
                    }
                )
        # Query notion db with async API.
        response = await self.notion.databases.query(
            database_id=self.knowledge_source_uri,
            filter=filter_params,
        )

        # Format the data.
        doc_list = []
        for item in response["results"]:
            url = ""
            url_block = item["properties"].get("URL", None)
            if url_block:
                url = url_block["rich_text"][0]["plain_text"]
            else:
                self.logger.warning("No url found.")
            summary = item["properties"]["Summary"]["rich_text"][0]["plain_text"]
            doc = {
                "Title": item["properties"]["Title"]["title"][0]["plain_text"],
                "Summary": summary[:300],
                "url": url,
            }
            doc_list.append(doc)
        return doc_list

    async def _generate_report(self, doc_list: List[Dict[str, Any]]):
        """Generate the report for the given doc_list.

        Args:
            doc_list (List[Dict[str, Any]]): The list of docs.
        """
        today = date.today()
        formatted_date = today.strftime("%Y/%m/%d")
        json_string = json.dumps(doc_list)
        content_prompt = f"""
        '''
        Report of {formatted_date}

        {json_string}
        '''
        """
        # Truncate.
        truncate_size = 4000 if self.model_type == "gpt-3.5-turbo" else 8000
        content_prompt = content_prompt[:truncate_size]
        self.logger.output(f"Content prompt: {content_prompt}")
        # Rough estimation of remaining tokens for generation.
        prompt_tokens = len(content_prompt)
        max_tokens = int(truncate_size - min(truncate_size, prompt_tokens) * 0.5)
        self.logger.output(
            f"Prompt tokens: {prompt_tokens}, response tokens: {max_tokens}"
        )
        response = openai.ChatCompletion.create(
            model=self.model_type,
            messages=[
                {
                    "role": "system",
                    "content": f"{self.report_prompt}",
                },
                {"role": "user", "content": content_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        result = response.choices[0].message.content
        return result
