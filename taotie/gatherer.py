"""Gather data from different sources and use the consumer to process the received messages.
"""
import asyncio
import time
from queue import Queue
from threading import Thread

from taotie.consumer.base import Consumer
from taotie.utils import Logger


class Gatherer(Thread):
    """Gather data from different sources and use the consumer to process the received messages."""

    def __init__(
        self,
        queue: Queue,
        consumer: Consumer,
        batch_size: int = 1,
        fetch_interval: int = 5,
        verbose: bool = False,
    ):
        """Initialize the gatherer.

        Args:
            queue (Queue): The queue to store the messages.
            consumer (Consumer): The consumer to process the messages.
            batch_size (int, optional): The batch size to process the messages. Defaults to 1.
            fetch_interval (int, optional): The interval to fetch the messages. Defaults to 5.
            verbose (bool, optional): Whether to print the log. Defaults to False.
        """
        Thread.__init__(self)
        self.logger = Logger(logger_name=__name__, verbose=verbose)
        self.queue = queue
        self.batch_size = batch_size
        self.verbose = verbose
        self.comsumer = consumer
        self.fetch_interval = fetch_interval
        self.logger.info("Gatherer initialized.")

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.get_event_loop().run_until_complete(self._execute())

    async def _execute(self):
        while True:
            if self.queue.empty():
                await asyncio.sleep(self.fetch_interval)
            fetch_count = 0
            messages = []
            while not self.queue.empty() and fetch_count < self.batch_size:
                fetch_count += 1
                messages.append(self.queue.get())
                self.queue.task_done()
            self.logger.info(f"Received: {len(messages)} {messages}")
            asyncio.create_task(self.comsumer.process(messages))
