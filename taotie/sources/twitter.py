import atexit
import os
from datetime import datetime
from typing import List

import requests
import tweepy
from tweepy import StreamingClient, StreamRule

from taotie.sources.base import BaseSource
from taotie.utils import *


class TwitterSubscriber(StreamingClient, BaseSource):
    """Listen to Twitter stream according to the rules.

    Args:
        rules (List[StreamRule]): List of rules to filter the stream.
        Please check https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/integrate/build-a-rule#availability
        on how to define the rules.
    """

    def __init__(
        self,
        rules: List[str],
        **kwargs,
    ):
        BaseSource.__init__(self)
        load_dotenv()
        self.bearer_token = os.getenv("BEARER_TOKEN")
        StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        self.logger = Logger(os.path.basename(__file__))
        self.cleanup()  # Do a pre-cleanup.
        self.add_filter_rules(rules)
        atexit.register(self.cleanup)

    def add_filter_rules(self, rules: List[str]):
        """Add rules to filter the stream."""
        rules = [StreamRule(value=rule) for rule in rules]
        response = self.add_rules(rules)
        self.logger.info(f"Add rules: {response}")

    def on_tweet(self, tweet):
        print(f"{datetime.now()} (Id: {tweet.id}):\n{tweet}")

    def cleanup(self):
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


rules = ["from:RetroSummary", "#GPT", "#llm"]
subscriber = TwitterSubscriber(rules=rules)
subscriber.start()
