"""The main entry to collect the information from all the sources.
"""
import asyncio
import json
import os
from typing import Any, Dict, List

from colorama import Fore

from taotie.consumer.base import Consumer
from taotie.gatherer import Gatherer
from taotie.message_queue import SimpleMessageQueue
from taotie.orchestrator import Orchestrator
from taotie.sources.github import GithubTrends
from taotie.sources.http_service import HttpService
from taotie.sources.twitter import TwitterSubscriber

try:
    import openai
except ImportError:
    print("Please install openai first: pip install openai")


class SummaryConsumer(Consumer):
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


def create_info_printer():
    verbose = True
    batch_size = 1
    fetch_interval = 10
    mq = SimpleMessageQueue()
    consumer = SummaryConsumer(
        buffer_size=1000, verbose=verbose, dedup=True, max_tokens=1800
    )
    gatherer = Gatherer(
        message_queue=mq,
        consumer=consumer,
        batch_size=batch_size,
        fetch_interval=fetch_interval,
        verbose=verbose,
    )

    # Twitter source.
    rules = [
        "from:RetroSummary",
        "from:RunGreatClasses",
        "#GPT",
        "#llm",
        "#AI",
        "#AGI",
        "foundation model",
    ]
    # it will be a bit tricky to test twitter api, as it's no longer free.
    # https://twitter.com/TwitterDev/status/1621026986784337922 
    #twitter_source = TwitterSubscriber(rules=rules, sink=mq, verbose=verbose)
    # Github source.
    github_source = GithubTrends(sink=mq, verbose=verbose)
    # Http service source.
    http_service_source = HttpService(sink=mq, verbose=verbose, truncate_size=3000)

    orchestrator = Orchestrator()
    orchestrator.set_gatherer(gatherer=gatherer)
    # orchestrator.add_source(twitter_source)
    # orchestrator.add_source(github_source)
    orchestrator.add_source(http_service_source)
    orchestrator.start()


if __name__ == "__main__":
    create_info_printer()
