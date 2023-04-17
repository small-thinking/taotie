"""The message queue is used to store the messages sent by the sources and consumed by the consumer.
"""
import json
from abc import ABC, abstractmethod
from asyncio import Queue
from typing import List

from taotie.utils import Logger


class MessageQueue(ABC):
    def __init__(self, verbose: bool = False):
        self.logger = Logger(logger_name=__name__, verbose=verbose)

    async def put(self, message_json: str) -> bool:
        # Validate the message.
        try:
            json.loads(message_json)
        except json.JSONDecodeError:
            return False
        await self._put(message_json)
        return True

    @abstractmethod
    async def _put(self, message_json: str):
        """Put the message into the message queue."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, batch_size: int = 1) -> List[str]:
        """Extract the message from the message queue.
        It is possible to get multiple messages at a time.
        """
        raise NotImplementedError

    @abstractmethod
    def empty(self) -> bool:
        """Check if the message queue is empty."""
        raise NotImplementedError


class SimpleMessageQueue(MessageQueue):
    """A warpper of the built-in thread-safe queue.Queue."""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self.queue: Queue = Queue()

    async def _put(self, message_json: str):
        await self.queue.put(message_json)

    async def get(self, batch_size: int = 1) -> List[str]:
        fetch_count = 0
        messages = []
        while not self.queue.empty() and fetch_count < batch_size:
            fetch_count += 1
            messages.append(self.queue.get())
            self.queue.task_done()
        return messages

    def empty(self) -> bool:
        return self.queue.empty()
