import os
from datetime import datetime
from typing import List

import tweepy

from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource, Information
from taotie.utils import get_datetime


class TwitterSubscriber(BaseSource):
    """Listen to Twitter stream according to the rules.

    Args:
        rules (List[str]): List of rules to filter the stream.
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
        auth = tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET_KEY"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        )
        self.stream = tweepy.Stream(auth=auth, listener=self)
        self._cleanup()  # Do a pre-cleanup.
        self.add_filter_rules(rules)
        self.batch = []
        self.batch_send_size = kwargs.get("batch_send_size", 5)
        self.logger.info(f"Twitter subscriber initialized.")

    def add_filter_rules(self, rules: List[str]):
        """Add rules to filter the stream."""
        self.stream.filter(track=rules)

    def on_status(self, status):
        self.logger.debug(f"{datetime.now()} (Id: {status.id}):\n{status}")
        tweet = Information(
            type="tweet",
            datetime_str=status.created_at or get_datetime(),
            id=status.id,
            text=status.text,
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
        self.stream.filter(threaded=True)

