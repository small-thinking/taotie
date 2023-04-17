"""
"""
import asyncio
import os
import signal
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

    async def run(self):
        if not self.sources:
            self.logger.error("No sources are added.")
            return
        if not self.gatherer:
            self.logger.error("No gatherer is set.")
            return

        tasks = {}
        for source in self.sources.values():
            tasks[source.__class__.__name__] = asyncio.create_task(source.run())
        tasks[self.gatherer.__class__.__name__] = asyncio.create_task(
            self.gatherer.run()
        )

        # Add a signal handler to stop tasks on KeyboardInterrupt
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.stop_tasks, tasks)

        await asyncio.gather(*tasks.values())

    def stop_tasks(self, tasks):
        for name, task in tasks.items():
            self.logger.info(f"Stopping task {name}...")
            if isinstance(task, Gatherer):
                task._running = False
            task.cancel()
        asyncio.get_event_loop().stop()
        self.logger.info("All tasks stopped.")
