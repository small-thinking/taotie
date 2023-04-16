"""
"""
import asyncio
import json
import os
from typing import Any, Dict, List

import openai
from colorama import Fore

from taotie.consumer.base import Consumer


class SimpleSummarizer(Consumer):
    """A consumer that summarize the message in batch."""

    def __init__(self, verbose: bool = False, dedup: bool = False, **kwargs):
        Consumer.__init__(self, verbose=verbose, dedup=dedup)
        self.buffer, self.buffer_size = [], 0
        self.max_buffer_size = kwargs.get("max_buffer_size", 800)
        self.language = kwargs.get("language", "English")
        self.max_tokens = kwargs.get("max_tokens", 800)
        self.logger.info("PrintConsumer initialized.")

    async def _process(self, messages: List[Dict[str, Any]]):
        self.buffer.extend(map(lambda m: json.dumps(m), messages))
        if len("".join(self.buffer)) > self.max_buffer_size:
            concatenated_messages = "\n".join(self.buffer)
            self.logger.info(f"Raw information: {concatenated_messages}\n")
            asyncio.create_task(self.gpt_summary(concatenated_messages))
            self.buffer.clear()

    async def gpt_summary(self, input: str) -> str:
        """A tiny example use case of using LLM to process the gathered information."""
        input = input[: self.max_buffer_size]
        prompt = f"""
        Please summarize the following collected json data in an informative way in {self.language}:
        If the json is about a tweets, please refer the id. If it does not contain meaningful information, please ignore it.
        If the json is about a github repos, please summarize them ONE BY ONE and include the repo names and the repo links.

        {input}
        """
        if not os.getenv("OPENAI_API_KEY"):
            return "Please set OPENAI_API_KEY in .env."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that extracts and summarizes the meaningful information from the collected json data."
                    f"Please summarize in {self.language}",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        self.logger.output(
            f"Summary: {response.choices[0].message.content}\n", color=Fore.BLUE
        )
