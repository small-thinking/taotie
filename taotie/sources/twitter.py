import asyncio
import concurrent.futures
import os
from typing import List

import requests  # type: ignore
from tweepy import StreamingClient, StreamRule  # type: ignore

from taotie.entity import Information
from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource
from taotie.utils.utils import Logger, get_datetime, load_dotenv


class TwitterSubscriber(BaseSource):
    """Listen to Twitter stream according to the rules.

    Args:
        rules (List[StreamRule]): List of rules to filter the stream.
        Please check https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/integrate/build-a-rule#availability
        on how to define the rules.
    """

    def __init__(
        self,
        rules: List[str],
        sink: MessageQueue,
        verbose: bool = False,
        **kwargs,
    ):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        self.internal_queue: asyncio.Queue = asyncio.Queue()
        # Tweepy is sync, so has to be wrapped in an executor.
        self.sync_twitter_subscriber = SyncTwitterSubscriber(
            rules=rules, internal_queue=self.internal_queue, verbose=verbose, **kwargs
        )
        self.batch: List[Information] = []
        self.batch_send_size = kwargs.get("batch_send_size", 1)
        self.logger.info(f"Twitter subscriber initialized.")

    async def run(self):
        loop = asyncio.get_event_loop()
        # Create an executor to run the sync method in a separate thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, self.sync_twitter_subscriber.run)
        while True:
            tweet: Information = await self.internal_queue.get()  # type: ignore
            self.batch.append(tweet)
            if len(self.batch) >= self.batch_send_size:
                await asyncio.gather(*(self._send_data(t) for t in self.batch))
                self.batch.clear()

    async def _cleanup(self):
        pass


class SyncTwitterSubscriber(StreamingClient):
    def __init__(
        self,
        rules: List[str],
        internal_queue: asyncio.Queue,
        verbose: bool = False,
        **kwargs,
    ):
        load_dotenv()
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)
        self.internal_queue = internal_queue
        self._cleanup()  # Do a pre-cleanup.
        self.add_filter_rules(rules)

    def add_filter_rules(self, rules: List[str]):
        """Add rules to filter the stream."""
        rules = [StreamRule(value=rule) for rule in rules]
        response = self.add_rules(rules)
        self.logger.info(f"Add rules: {response}")

    def on_tweet(self, tweet):
        author_id = tweet.author_id if tweet.author_id else "unknown"
        tweet_info = Information(
            type="tweet",
            datetime_str=tweet.created_at or get_datetime(),
            id=tweet.id,
            uri=f"https://twitter.com/{author_id}/status/{tweet.id}",
            content=tweet.text,
        )
        # Put the tweet in the queue, no need to await since the queue is a thread-safe data structure.
        self.internal_queue.put_nowait(tweet_info)

    def _cleanup(self):
        # Fetch all rules.
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(
            "https://api.twitter.com/2/tweets/search/stream/rules", headers=headers
        )

        if response.status_code != 200:
            raise Exception(
                f"Cannot get rules (HTTP {response.status_code}): {response.text}"
            )
        else:
            response = response.json()
            # Delete all rules.
            rule_ids = []
            if "data" in response:
                rule_ids = [rule["id"] for rule in response["data"]]
                response = self.delete_rules(rule_ids)
                self.logger.info(f"Deleted rules: {response}")

    def run(self):
        self.filter(threaded=True)
