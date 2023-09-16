"""The message queue is used to store the messages sent by the sources and consumed by the consumer.
"""
import asyncio
import json
from abc import ABC, abstractmethod
from asyncio import Queue
from typing import List

from redis import asyncio as aioredis  # type: ignore

from taotie.utils.utils import Logger


class MessageQueue(ABC):
    def __init__(self, verbose: bool = False):
        self.logger = Logger(logger_name=__name__, verbose=verbose)

    async def connect(self):
        """Connect to the message queue."""
        pass

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
    async def empty(self) -> bool:
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
        while self.queue.qsize() > 0 and fetch_count < batch_size:
            fetch_count += 1
            messages.append(await self.queue.get())
        return messages

    async def empty(self) -> bool:
        return self.queue.qsize() == 0


class RedisMessageQueue(MessageQueue):
    def __init__(self, redis_url: str, channel_name: str, verbose: bool = False):
        """
        Initialize the RedisMessageQueue.

        :param redis_url: URL of the Redis server.
        :param channel_name: Name of the pub/sub channel to use.
        :param verbose: Whether to log verbose output or not.
        """
        super().__init__(verbose=verbose)
        self.redis_url = redis_url
        self.channel_name = channel_name

    async def connect(self):
        """Connect to the Redis server and subscribe to the channel."""
        self.pool = aioredis.ConnectionPool(host=self.redis_url, db=0)
        self.redis = await aioredis.Redis(connection_pool=self.pool)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        res = await self.pubsub.subscribe(self.channel_name)
        return res

    async def close(self):
        """Unsubscribe from the channel and close the Redis connection."""
        if self.pubsub:
            await self.pubsub.unsubscribe(self.channel_name)
            self.pubsub = None
        if self.redis:
            await self.redis.close()

    async def _put(self, message_json: str):
        """Publish the message to the Redis channel."""
        await self.redis.publish(self.channel_name, message_json)

    async def get(self, batch_size: int = 1) -> List[str]:
        """Get messages from the Redis channel up to the batch_size limit."""
        messages = []
        count = 0
        while count < batch_size:
            msg = await self.pubsub.get_message()
            if msg is None:
                await asyncio.sleep(0.1)
                continue
            messages.append(msg["data"].decode("utf-8"))
            count += 1
        return messages

    async def empty(self) -> bool:
        """
        Check if the message queue is empty.

        Redis pub/sub doesn't support checking if a channel is empty, so this method always returns False.
        """
        return False
