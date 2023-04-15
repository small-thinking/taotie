"""The simplest consumer that prints the message to the console.
"""
from taotie.consumer.base import Consumer


class PrintConsumer(Consumer):
    """A consumer that prints the message."""

    def __init__(self, verbose: bool = False, **kwargs):
        Consumer.__init__(self, verbose=verbose)
        self.logger.info("PrintConsumer initialized.")

    async def process(self, messages):
        self.logger.output(f"PrintConsumer: {messages}\n")
