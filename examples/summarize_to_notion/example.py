"""The main entry to collect the information from all the sources.
"""
import asyncio
import os

from taotie.consumer.simple_summarizer import SimpleSummarizer
from taotie.gatherer import Gatherer
from taotie.message_queue import RedisMessageQueue, SimpleMessageQueue
from taotie.orchestrator import Orchestrator
from taotie.sources.github import GithubTrends
from taotie.sources.http_service import HttpService
from taotie.sources.twitter import TwitterSubscriber
from taotie.storage.memory import DedupMemory
from taotie.storage.notion import NotionStorage
from taotie.utils import load_env


def create_notion_summarizer():
    load_env()  # This has to be called as early as possible.

    verbose = True
    batch_size = 1
    fetch_interval = 10
    redis_url = "taotie-redis"
    channel_name = "taotie"
    mq = RedisMessageQueue(redis_url=redis_url, channel_name=channel_name, verbose=True)
    instruction = None
    storage = NotionStorage(
        root_page_id=os.getenv("NOTION_ROOT_PAGE_ID"), verbose=verbose
    )
    dedup_memory = DedupMemory(redis_url=redis_url)
    consumer = SimpleSummarizer(
        buffer_size=1000,
        summarize_instruction=instruction,
        verbose=verbose,
        dedup=True,
        storage=storage,
        max_tokens=1000,
        max_buffer_size=1000,
    )
    gatherer = Gatherer(
        message_queue=mq,
        consumer=consumer,
        batch_size=batch_size,
        fetch_interval=fetch_interval,
        verbose=verbose,
    )
    orchestrator = Orchestrator(verbose=verbose)
    orchestrator.set_gatherer(gatherer=gatherer)

    # Twitter source.
    # rules = ["from:RunGreatClasses", "#GPT", "#llm", "#AI", "#AGI", "foundation model"]
    # twitter_source = TwitterSubscriber(rules=rules, sink=mq, verbose=verbose)
    # orchestrator.add_source(twitter_source)
    # Github source.
    github_source = GithubTrends(sink=mq, verbose=verbose, dedup_memory=dedup_memory)
    orchestrator.add_source(github_source)
    # # Http service source.
    http_service_source = HttpService(
        sink=mq, verbose=verbose, dedup_memory=dedup_memory, truncate_size=200000
    )
    orchestrator.add_source(http_service_source)
    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    create_notion_summarizer()
