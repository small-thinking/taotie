"""
"""
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import openai
from colorama import Fore

from taotie.consumer.base import Consumer
from taotie.storage.base import Storage


class SimpleSummarizer(Consumer):
    """A consumer that summarize the message in batch."""

    def __init__(
        self,
        summarize_instruction: str,
        verbose: bool = False,
        dedup: bool = False,
        storage: Optional[Storage] = None,
        **kwargs,
    ):
        Consumer.__init__(self, verbose=verbose, dedup=dedup, storage=storage, **kwargs)
        self.buffer: List[str] = []
        self.buffer_size = 0
        self.max_buffer_size = kwargs.get("max_buffer_size", 800)
        self.summarize_instruction = summarize_instruction
        if not self.summarize_instruction:
            self.summarize_instruction = """
            Please summarize the following collected json data in an informative way in English:
            If the json is about a tweets, please refer the id. If it does not contain meaningful information, please ignore it.
            If the json is about a github repos, please summarize them ONE BY ONE and include the repo names and the repo links.
            """
        self.max_tokens = kwargs.get("max_tokens", 800)
        self.logger.info("PrintConsumer initialized.")

    async def _process(self, messages: List[Dict[str, Any]]) -> None:
        self.buffer.extend(map(lambda m: json.dumps(m), messages))
        if len("".join(self.buffer)) > self.max_buffer_size:
            concatenated_messages = "\n".join(self.buffer)
            self.logger.info(f"Raw information: {concatenated_messages}\n")
            summary = await asyncio.create_task(self.gpt_summary(concatenated_messages))
            self.logger.output(f"Summary: {summary}\n", color=Fore.BLUE)
            # Save to storage.
            if self.storage:
                processed_data = {"summary": summary}
                list_of_tuples = [(raw, processed_data) for raw in messages]
                await self.storage.save(list_of_tuples)
                self.logger.info(f"Saved to storage.")

            self.buffer.clear()

    async def gpt_summary(self, input: str) -> str:
        """A tiny example use case of using LLM to process the gathered information."""
        input = input[: self.max_buffer_size]
        prompt = f"""
        {self.summarize_instruction}
        {input}
        """
        if not os.getenv("OPENAI_API_KEY"):
            return "Please set OPENAI_API_KEY in .env."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"{self.summarize_instruction}",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        result = response.choices[0].message.content
        return result
