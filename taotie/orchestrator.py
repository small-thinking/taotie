"""
"""
import asyncio
import os
from threading import Thread
from typing import Dict

from taotie.gatherer import Gatherer
from taotie.sources.base import BaseSource
from taotie.utils import Logger


class Orchestrator:
    """The main entry to collect the information from all the sources."""

    def __init__(self, verbose: bool = False):
        self.sources: Dict[str, BaseSource] = {}
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)

    def add_source(self, source: BaseSource):
        self.sources[str(source)] = source

    def set_gatherer(self, gatherer: Gatherer):
        self.gatherer = gatherer

    async def start(self):
        if not self.sources:
            self.logger.error("No sources are added.")
            return
        if not self.gatherer:
            self.logger.error("No gatherer is set.")
            return

        tasks = []
        for source in self.sources.values():
            tasks.append(asyncio.create_task(source.start()))
        tasks.append(asyncio.create_task(self.gatherer.start()))

        await asyncio.gather(*tasks)
