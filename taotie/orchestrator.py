"""The main entry to collect the information from all the sources.
"""
import argparse
import asyncio
import os
from queue import Queue
from threading import Thread

from taotie.consumer.print_consumer import PrintConsumer
from taotie.gatherer import Gatherer
from taotie.sources.base import BaseSource
from taotie.sources.github import GithubEvent
from taotie.sources.twitter import TwitterSubscriber
from taotie.utils import Logger


class Orchestrator(Thread):
    """The main entry to collect the information from all the sources."""

    def __init__(self, verbose: bool = False):
        super().__init__()
        self.sources = {}
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)

    def add_source(self, source: BaseSource):
        self.sources[str(source)] = source

    def set_gatherer(self, gatherer: Gatherer):
        self.gatherer = gatherer

    def run(self):
        for source in self.sources.values():
            source.start()
        self.gatherer.start()
        self.gatherer.join()
        for source in self.sources.values():
            source.join()


def run(args: argparse.Namespace):
    queue = Queue()
    consumer = PrintConsumer()
    gatherer = Gatherer(queue=queue, consumer=consumer, verbose=args.verbose)

    # Twitter source.
    rules = ["from:RetroSummary", "from:RunGreatClasses", "#GPT", "#llm"]
    twitter_source = TwitterSubscriber(rules=rules, sink=queue, verbose=args.verbose)

    # Github source.
    github_source = GithubEvent(sink=queue, verbose=args.verbose)

    orchestrator = Orchestrator()
    orchestrator.set_gatherer(gatherer=gatherer)
    orchestrator.add_source(twitter_source)
    orchestrator.add_source(github_source)
    orchestrator.start()


def parse_args():
    parser = argparse.ArgumentParser(description="Orchestrator")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args)
