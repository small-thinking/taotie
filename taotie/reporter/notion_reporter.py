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
        type_filters: List[str],
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
        self.type_filters = type_filters
        self.topic_filters = topic_filters
        # Model configs.
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("Please set OPENAI_API_KEY in .env.")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.model_type = kwargs.get("model_type", "gpt-3.5-turbo-16k-0613")
        # Prompt.
        language = kwargs.get("language", "Chinese")
        if "github-repo" in self.topic_filters:
            self.report_prompt = f"""
            Please generate a report that will be published by the WECHAT BLOG based on the json string in the triple quotes.
            Follow the following rules STRICTLY:
            1. Summarize in {language} and at the beginning give a short overall summary of the repos in this report.
            2. Skip the items that are not relevant to AI or the topics of {self.topic_filters}.
            3. Generate each item as an individual section, include the URL in each of the item, and \
                including the strength of recommendation (draw 1-5 stars) and the reason to recommend. \
                Make the summary as informative as possible.
            4. If the item is about a paper, please emphasis the afflication of the authors if it is famous.
            5. Generate the description in an attractive way, so that the readers will be willing to check the content.
            6. Rank by importance (e.g. whether has image) and keep AT MOST the top 10 items based on the recommendation strength.
            7. Output the results as a JSON string which contains a list of items (with keys "Title", "Rating", "Summary", "Reason", "URL"). Example:

            {{
                "results": [
                    {{
                        "Title": "【★★★★★】TransformerOptimus/SuperAGI",
                        "Summary": "这是一个用于构建和运行有用的自主智能体的Python项目。",
                        "Reason": "自主性AI最新版本。该项目旨在创造一个可以解决朴实问题的自主智能体。",
                        "URL": "https://github.com/TransformerOptimus/SuperAGI",
                    }},
                    {{
                        "Title": "【★★★★】LLM-ToolMaker",
                        "Summary": "这个项目提出了一种名为LLMs As Tool Makers (LATM)的闭环框架，其中大型语言模型(LLMs)可以作为工具制造者为解决问题创造自己的可重用工具。",
                        "Reason": "开放框架。该项目旨在创造一个可以使用外部工具的自主智能体。",
                        "URL": "https://github.com/ctlllll/LLM-ToolMaker",
                    }}
                ]
            }}
            """
        else:
            self.report_prompt = f"""
            Please generate a report of the paper summary that will be published by the WECHAT BLOG based on the json string in the triple quotes.
            Follow the following rules STRICTLY:
            1. Summarize in {language} and at the beginning give a short overall summary of the repos in this report.
            2. SKIP the items that are not relevant to AI or the topics of {self.topic_filters}.
            3. use the paper name as the title for each item. Then followed by a short overall summary of the paper.
            4. Emphasis the authors or afflications if they famous.
            5. Generate each item as an individual section, include the URL in each of the item, and \
                including the strength of recommendation (draw 1-5 stars) and the reason to recommend. \
                Make the summary as informative as possible.
            6. Rank by importance (e.g. authors or affiliation) and only keep AT MOST the top 10 items based on the recommendation strength.
            7. Output the results as a JSON string which contains a list of items (with keys "Title", "Rating", "Summary", "Reason", "URL"). Example:
            {{
                "results": [
                    {{
                        "Title": "Training Language Models with Language Feedback at Scale",
                        "Summary": "本文介绍了一种新的语言反馈模型训练方法ILF，利用更具信息量的语言反馈来解决预训练语言模型生成的文本与人类偏好不一致的问题。",
                        "Reason": "新的语言反馈模型训练方法。",
                        "URL": "https://arxiv.org/abs/2303.16755v2",
                    }},
                    {{
                        "Title": "Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting",
                        "Summary": "本文研究了大型语言模型（LLMs）在链式思考推理（CoT）中的解释不忠实问题，揭示了CoT解释可能受到多种因素的影响。",
                        "Reason": "深入研究LLMs的行为。",
                        "URL": "http://arxiv.org/abs/2305.04388v1",
                    }}
                ]
            }}
            """

    async def _connect(self):
        self.notion = AsyncClient(auth=self.token)

    async def _cleanup(self):
        print("cleanup")

    async def _distill(self) -> str:
        """Grab the gathered knowledge from notion database and generate the text report.

        Returns:
            str: The text report.
        """
        doc_list = await self._retrieve_data()
        self.logger.output(f"Number docs retrieved: {len(doc_list)}\n")
        self.logger.output(json.dumps(doc_list, indent=2))
        report = await self._generate_report(doc_list)
        self.logger.output(f"{report}\n", color=Fore.BLUE)
        return report

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
                {"or": []},  # type filter.
                {"or": []},  # topic filter.
            ]
        }
        and_blob: List[Any] = filter_params["and"]
        # Add type filters.
        if self.type_filters:
            for type_filter in self.type_filters:
                and_blob[1]["or"].append(
                    {
                        "property": "Type",
                        "select": {"equals": type_filter},
                    }
                )
        # Add tag filters.
        if self.topic_filters:
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
        truncate_size = 12000 if self.model_type == "gpt-3.5-turbo-16k-0613" else 7000
        content_prompt = content_prompt[:truncate_size]
        self.logger.output(f"Content prompt: {content_prompt}")
        # Rough estimation of remaining tokens for generation.
        prompt_tokens = len(content_prompt)
        max_tokens = int(truncate_size - min(truncate_size, prompt_tokens) * 0.45)
        self.logger.output(
            f"Prompt tokens: {prompt_tokens}, response tokens: {max_tokens}"
        )
        result = chat_completion(
            model_type=self.model_type,
            prompt=self.report_prompt,
            content=content_prompt,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return result
