"""The main entry to collect the information from all the sources.
"""
import asyncio
import os
from queue import Queue

from colorama import Fore

from taotie.consumer.base import Consumer
from taotie.gatherer import Gatherer
from taotie.orchestrator import Orchestrator
from taotie.sources.github import GithubEvent
from taotie.sources.twitter import TwitterSubscriber

try:
    import openai
except ImportError:
    print("Please install openai first: pip install openai")


class SummaryConsumer(Consumer):
    """A consumer that summarize the message in batch."""

    def __init__(self, verbose: bool = False, **kwargs):
        Consumer.__init__(self, verbose=verbose)
        self.logger.info("PrintConsumer initialized.")
        self.buffer = ""
        self.buffer_size = kwargs.get("buffer_size") or 800
        self.language = kwargs.get("language") or "English"
        self.max_tokens = kwargs.get("max_tokens") or 500

    async def process(self, messages):
        self.buffer += f"{messages}\n"
        if len(self.buffer) > self.buffer_size:
            self.logger.info(f"Raw information: {self.buffer}\n")
            asyncio.create_task(self.gpt_summary(self.buffer))
            self.buffer = ""

    async def gpt_summary(self, input: str) -> str:
        """A tiny example use case of using LLM to process the gathered information."""
        prompt = f"""
        Please summarize the following information we collected in {self.language}.
        {input}
        """
        if not os.getenv("OPENAI_API_KEY"):
            return "Please set OPENAI_API_KEY in .env."
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.1,
        )
        self.logger.output(f"Summary: {response.choices[0].text}\n", color=Fore.BLUE)


def create_info_printer():
    verbose = True
    queue = Queue()
    consumer = SummaryConsumer(buffer_size=1000, language="Chinese")
    gatherer = Gatherer(
        queue=queue, consumer=consumer, fetch_interval=5, verbose=verbose
    )

    # Twitter source.
    rules = ["from:RetroSummary", "from:RunGreatClasses", "#GPT", "#llm"]
    twitter_source = TwitterSubscriber(rules=rules, sink=queue, verbose=verbose)
    # Github source.
    github_source = GithubEvent(sink=queue, verbose=verbose)

    orchestrator = Orchestrator()
    orchestrator.set_gatherer(gatherer=gatherer)
    orchestrator.add_source(twitter_source)
    orchestrator.add_source(github_source)
    orchestrator.start()


if __name__ == "__main__":
    create_info_printer()
