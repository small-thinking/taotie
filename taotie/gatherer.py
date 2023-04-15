"""Gather data from different sources and use the consumer to process the received messages.
"""
import asyncio
import time
from queue import Queue
from threading import Thread

from taotie.consumer.consumer import Consumer
from taotie.utils import Logger


class Gatherer(Thread):
    """Gather data from different sources and use the consumer to process the received messages."""

    def __init__(
        self,
        queue: Queue,
        consumer: Consumer,
        verbose: bool = False,
    ):
        Thread.__init__(self)
        self.logger = Logger(logger_name=__name__, verbose=verbose)
        self.queue = queue
        self.verbose = verbose
        self.comsumer = consumer
        self.logger.info("Gatherer initialized.")

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.get_event_loop().run_until_complete(self._execute())

    async def _execute(self):
        while True:
            if self.queue.empty():
                await asyncio.sleep(1)
            message = self.queue.get()
            self.logger.debug(f"Received: {message}")
            asyncio.create_task(self.comsumer.process(message))
            self.queue.task_done()
