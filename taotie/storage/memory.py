"""This module contains the memory implementation of the storage.
"""
import os
import time
from typing import Optional

from redis import asyncio as aioredis  # type: ignore

from taotie.utils import Logger, load_dotenv


class DedupMemory:
    """This is a memory implementation of the storage.
    It uses a Redis server to store the indexed data.
    """

    def __init__(self, redis_url: str, verbose: bool = False, **kwargs):
        self.verbose = verbose
        load_dotenv()
        self.logger = Logger(os.path.basename(__file__), verbose=verbose)
        self.redis_url = redis_url
        self.connected = False

    async def connect(self):
        """Connect to the Redis server and subscribe to the channel."""
        self.pool = aioredis.ConnectionPool(host=self.redis_url, db=0)
        self.redis = await aioredis.Redis(connection_pool=self.pool)

    async def close(self):
        if not self.connected:
            return
        await self.redis.close()

    async def save_or_overwrite(self, key: str, ttl: Optional[int] = None):
        """The value is the timestamp by default.
        If ttl provided, overwrite if the existing value is older than ttl.
        """
        if not self.connected:
            await self.connect()
            self.connected = True
        timestamp = int(time.time())
        value = str(timestamp)
        if ttl is not None:
            # Not save if the existing value has not expired
            existing_timestamp = await self.get(key)
            if (
                existing_timestamp is not None
                and int(existing_timestamp) > timestamp - ttl
            ):
                if self.verbose:
                    self.logger.info(f"Key: {key} exists. Won't renew.")
                return
        await self.redis.set(key, value)

    async def check_and_save(self, key: str, ttl: Optional[int] = None):
        """Check whether the key already exists, insert if not exist before.
        If ttl provided, overwrite if the existing value is older than ttl.
        """
        if not self.connected:
            await self.connect()
            self.connected = True
        if await self.exists(key):
            if self.verbose:
                self.logger.warning(f"Key: {key} exists. Won't renew.")
            return
        await self.save_or_overwrite(key, ttl)

    async def exists(self, key: str):
        if not self.connected:
            await self.connect()
            self.connected = True
        return await self.redis.exists(key)

    async def delete(self, key: str):
        if not self.connected:
            await self.connect()
            self.connected = True
        await self.redis.delete(key)

    async def get(self, key: str):
        if not self.connected:
            await self.connect()
            self.connected = True
        return await self.redis.get(key, encoding="utf-8")
