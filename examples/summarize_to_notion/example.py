"""The main entry to collect the information from all the sources.
"""
import asyncio
import os
import argparse

import os

from taotie.consumer.info_summarizer import InfoSummarizer
from taotie.gatherer import Gatherer
from taotie.message_queue import RedisMessageQueue
from taotie.orchestrator import Orchestrator
from taotie.sources.arxiv import Arxiv
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
    consumer = InfoSummarizer(
        buffer_size=1000,
        summarize_instruction=instruction,
        verbose=verbose,
        dedup=False,
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

    # Http service source.
    http_service_source = HttpService(
        sink=mq, verbose=verbose, dedup_memory=dedup_memory, truncate_size=200000
    )
for source in data_sources:
        if source == 'http_service':
            http_service_source = HttpService(sink=mq, verbose=verbose, dedup_memory=dedup_memory, truncate_size=200000)
            orchestrator.add_source(http_service_source)
        elif source == 'github':
            github_source = GithubTrends(sink=mq, verbose=verbose, dedup_memory=dedup_memory)
            orchestrator.add_source(github_source)
        elif source == 'arxiv':
            arxiv_source = Arxiv(sink=mq, verbose=verbose, dedup_memory=dedup_memory)
            orchestrator.add_source(arxiv_source)
elif source == 'twitter':
    rules = args.twitter_rules.split(',')
    twitter_source = TwitterSubscriber(rules=rules, sink=mq, verbose=verbose)
    orchestrator.add_source(twitter_source)
            orchestrator.add_source(arxiv_source)
    orchestrator.add_source(arxiv_source)

    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Specify data sources for the script.')
parser.add_argument('--data-sources', dest='data_sources', default='http_service', help='A comma-separated list of data sources to use (default: http_service)')
parser.add_argument('--twitter-rules', dest='twitter_rules', default='', help='A comma-separated list of rules for the Twitter source')
    parser.add_argument('--data-sources', dest='data_sources', default='http_service', help='A comma-separated list of data sources to use (default: http_service)')
    args = parser.parse_args()
    data_sources = args.data_sources.split(',')
    create_notion_summarizer(data_sources)
    create_notion_summarizer(data_sources, args.twitter_rules)
    create_notion_summarizer()
