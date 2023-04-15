"""Consumer the data collected by the gatherer.

"""
from abc import ABC, abstractmethod

from taotie.utils import Logger


class Consumer(ABC):
    """A concrete consumer would inherit from the Consumer class and implement the process method.
    The logic inside the process can be as simple as printing the message or as complex as an
    orchestrator such as a langchain application.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = Logger(logger_name=__name__, verbose=verbose)

    @abstractmethod
    async def process(self, message):
        """Process the message."""
        raise NotImplementedError
