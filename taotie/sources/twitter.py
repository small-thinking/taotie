from datetime import datetime
from queue import Queue
from typing import List

import requests
from tweepy import StreamRule

from taotie.sources.base import BaseSource, Information


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
        sink: Queue,
        verbose: bool = False,
        **kwargs,
    ):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.add_filter_rules(rules)
        self.logger.info(f"Twitter subscriber initialized.")

    def add_filter_rules(self, rules: List[str]):
        """Add rules to filter the stream."""
        rules = [StreamRule(value=rule) for rule in rules]
        response = self.add_rules(rules)
        self.logger.info(f"Add rules: {response}")

    def on_tweet(self, tweet):
        self.logger.debug(f"{datetime.now()} (Id: {tweet.id}):\n{tweet}")
        tweet = Information(
            type="tweet", timestamp=tweet.created_at, id=id, text=tweet.text
        )
        self._send_data(tweet)

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


# queue = Queue()
# rules = ["from:RetroSummary", "from:RunGreatClasses", "#GPT", "#llm"]
# subscriber = TwitterSubscriber(rules=rules, sink=queue, verbose=True)
# subscriber.start()
