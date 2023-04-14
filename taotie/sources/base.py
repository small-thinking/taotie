import atexit
import os
from abc import ABC, abstractmethod
from threading import Thread

from tweepy import StreamingClient

from taotie.utils import *


class BaseSource(ABC, Thread, StreamingClient):
    """Base class for all sources.

    This class is used to provide a common interface for all sources. It
    provides a method to get the source name and a method to get the
    source data.

    """

    def __init__(self, **kwargs):
        Thread.__init__(self)
        self.logger = Logger(os.path.basename(__file__))
        load_dotenv()
        self.bearer_token = os.getenv("BEARER_TOKEN")
        StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        self._cleanup()  # Do a pre-cleanup.
        atexit.register(self._cleanup)

    @abstractmethod
    def _cleanup(self):
        """Clean up the source."""
        pass

    @abstractmethod
    def run(self):
        """Listen to the source and return the data."""
        pass
