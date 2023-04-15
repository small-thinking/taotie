"""The main entry to collect the information from all the sources.
"""
import asyncio
import os

from colorama import Fore

from taotie.consumer.base import Consumer
from taotie.gatherer import Gatherer
from taotie.message_queue import SimpleMessageQueue
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
        self.buffer = []
        self.buffer_size = kwargs.get("buffer_size") or 800
        self.language = kwargs.get("language") or "English"
        self.max_tokens = kwargs.get("max_tokens") or 500

    async def process(self, messages):
        self.buffer.extend(messages)
        if len("".join(self.buffer)) > self.buffer_size:
            concatenated_messages = "\n".join(self.buffer)
            self.logger.info(f"Raw information: {concatenated_messages}\n")
            asyncio.create_task(self.gpt_summary(concatenated_messages))
            self.buffer.clear()

    async def gpt_summary(self, input: str) -> str:
        """A tiny example use case of using LLM to process the gathered information."""
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
    batch_size = 5
    fetch_interval = 10
    mq = SimpleMessageQueue()
    consumer = SummaryConsumer(buffer_size=1000, verbose=verbose, language="Chinese")
    gatherer = Gatherer(
        message_queue=mq,
        consumer=consumer,
        batch_size=batch_size,
        fetch_interval=fetch_interval,
        verbose=verbose,
    )

    # Twitter source.
    rules = ["from:RetroSummary", "from:RunGreatClasses", "#GPT", "#llm", "#AI", "#AGI"]
    twitter_source = TwitterSubscriber(rules=rules, sink=mq, verbose=verbose)
    # Github source.
    github_source = GithubEvent(sink=mq, verbose=verbose)

    orchestrator = Orchestrator()
    orchestrator.set_gatherer(gatherer=gatherer)
    orchestrator.add_source(twitter_source)
    orchestrator.add_source(github_source)
    orchestrator.start()


if __name__ == "__main__":
    create_info_printer()
