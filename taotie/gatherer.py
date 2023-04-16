"""Gather data from different sources and use the consumer to process the received messages.
"""
import asyncio
import json
from queue import Queue
from threading import Thread
from typing import Any, Dict, List

from taotie.consumer.base import Consumer
from taotie.utils import Logger


class Gatherer(Thread):
    """Gather data from different sources and use the consumer to process the received messages."""

    def __init__(
        self,
        message_queue: Queue,
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
        self.message_queue = message_queue
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
            while self.message_queue.empty():
                self.logger.info(
                    f"No messages, wait for {self.fetch_interval} seconds."
                )
                await asyncio.sleep(self.fetch_interval)
            else:
                messages = self.message_queue.get(batch_size=self.batch_size)
                messages = await self._filter(messages)
                self.logger.info(f"Gathered: {len(messages)} {messages}")
                asyncio.create_task(self.comsumer.process(messages))

    async def _filter(self, messages: List[str]) -> List[Dict[str, Any]]:
        """Filter the messages."""
        parsed_messages = list(map(lambda x: json.loads(x), messages))
        return parsed_messages
