"""Consumer the data collected by the gatherer.

"""
from abc import ABC, abstractmethod
from typing import List

from taotie.sources.base import Information
from taotie.utils import Logger


class Consumer(ABC):
    """A concrete consumer would inherit from the Consumer class and implement the process method.
    The logic inside the process can be as simple as printing the message or as complex as an
    orchestrator such as a langchain application.
    """

    def __init__(self, verbose: bool = False, **kwargs):
        self.verbose = verbose
        self.logger = Logger(logger_name=__name__, verbose=verbose)
        self.kwargs = kwargs

    @abstractmethod
    async def process(self, messages: List[Information]):
        """Process the message."""
        raise NotImplementedError
