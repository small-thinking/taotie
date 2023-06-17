"""Gather data from different sources and use the consumer to process the received messages.
"""
import asyncio
import json
from typing import Any, Dict, List

from taotie.consumer.base import Consumer
from taotie.message_queue import MessageQueue
from taotie.utils import Logger


class Gatherer:
    """Gather data from different sources and use the consumer to process the received messages."""

    def __init__(
        self,
        message_queue: MessageQueue,
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
        self.logger = Logger(logger_name=__name__, verbose=verbose)
        self.message_queue = message_queue
        self.batch_size = batch_size
        self.verbose = verbose
        self.consumer = consumer
        self.fetch_interval = fetch_interval
        self._running = True
        self.logger.info("Gatherer initialized.")

    async def run(self):
        try:
            self.logger.info(f"Connect to the message queue.")
            await self.message_queue.connect()
            while True:
                check_empty = await self.message_queue.empty()
                while check_empty:
                    self.logger.info(
                        f"No messages, wait for {self.fetch_interval} seconds."
                    )
                    await asyncio.sleep(self.fetch_interval)
                    check_empty = await self.message_queue.empty()
                    if not self._running:  # Add this check
                        raise asyncio.CancelledError
                else:
                    messages = await self.message_queue.get(batch_size=self.batch_size)
                    if not len(messages):
                        self.logger.info(
                            f"No messages, wait for {self.fetch_interval} seconds."
                        )
                        await asyncio.sleep(self.fetch_interval)
                        continue
                    messages: List[Dict[str, Any]] = await self._filter(messages)
                    await self.consumer.process(messages)
        except asyncio.CancelledError:
            self.logger.info("Gatherer canceled.")

    async def _filter(self, messages: List[str]) -> List[Dict[str, Any]]:
        """Filter the messages."""
        parsed_messages = list(map(lambda x: json.loads(x), messages))
        return parsed_messages
