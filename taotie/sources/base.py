import os
from abc import ABC, abstractmethod
from threading import Thread


class BaseSource(ABC, Thread):
    """Base class for all sources.

    This class is used to provide a common interface for all sources. It
    provides a method to get the source name and a method to get the
    source data.

    """

    def __init__(self):
        super().__init__()

    @abstractmethod
    def run(self):
        """Listen to the source and return the data."""
        pass
