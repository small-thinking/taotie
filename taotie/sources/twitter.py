import os
from datetime import datetime
from typing import List

import requests
from tweepy import StreamingClient, StreamRule

from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource, Information
from taotie.utils import get_datetime


class TwitterSubscriber(BaseSource, StreamingClient):
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
        StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        self._cleanup()  # Do a pre-cleanup.
        self.add_filter_rules(rules)
        self.batch = []
        self.batch_send_size = kwargs.get("batch_send_size", 5)
        self.logger.info(f"Twitter subscriber initialized.")

    def add_filter_rules(self, rules: List[str]):
        """Add rules to filter the stream."""
        rules = [StreamRule(value=rule) for rule in rules]
        response = self.add_rules(rules)
        self.logger.info(f"Add rules: {response}")

    def on_tweet(self, tweet):
        self.logger.debug(f"{datetime.now()} (Id: {tweet.id}):\n{tweet}")
        tweet = Information(
            type="tweet",
            datetime_str=tweet.created_at or get_datetime(),
            id=tweet.id,
            text=tweet.text,
        )
        self.batch.append(tweet)
        if len(self.batch) >= self.batch_send_size:
            map(lambda tweet: self._send_data(tweet), self.batch)
            self.batch.clear()

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
