"""The main entry to collect the information from all the sources.
"""
import asyncio
import os

from taotie.consumer.simple_summarizer import SimpleSummarizer
from taotie.gatherer import Gatherer
from taotie.message_queue import SimpleMessageQueue
from taotie.orchestrator import Orchestrator
from taotie.sources.github import GithubTrends
from taotie.sources.http_service import HttpService
from taotie.sources.twitter import TwitterSubscriber
from taotie.storage.notion import NotionStorage
from taotie.utils import load_env


def create_info_printer():
    load_env()  # This has to be called as early as possible.
    verbose = True
    batch_size = 1
    fetch_interval = 10
    mq = SimpleMessageQueue()
    instruction = """
    Please summarize the following collected json data in an informative way in Chinese.
    NO NEED TO MENTION TYPE. Just directly summarize the content in a CONCISE and COMPREHENSIvE way.
    """
    storage = NotionStorage(
        root_page_id=os.getenv("NOTION_ROOT_PAGE_ID"), verbose=verbose
    )
    consumer = SimpleSummarizer(
        buffer_size=1000,
        summarize_instruction=instruction,
        verbose=verbose,
        dedup=True,
        storage=storage,
        max_tokens=1800,
    )
    gatherer = Gatherer(
        message_queue=mq,
        consumer=consumer,
        batch_size=batch_size,
        fetch_interval=fetch_interval,
        verbose=verbose,
    )

    # Twitter source.
    rules = ["from:RunGreatClasses", "#GPT", "#llm", "#AI", "#AGI", "foundation model"]
    twitter_source = TwitterSubscriber(rules=rules, sink=mq, verbose=verbose)
    # Github source.
    github_source = GithubTrends(sink=mq, verbose=verbose)
    # # Http service source.
    # http_service_source = HttpService(sink=mq, verbose=verbose, truncate_size=3000)

    orchestrator = Orchestrator(verbose=verbose)
    orchestrator.set_gatherer(gatherer=gatherer)
    orchestrator.add_source(twitter_source)
    orchestrator.add_source(github_source)
    # orchestrator.add_source(http_service_source)
    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    create_info_printer()
