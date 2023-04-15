import atexit
import os
from abc import ABC, abstractmethod
from queue import Queue
from threading import Thread

from tweepy import StreamingClient

from taotie.utils import *


class Information:
    """This class is used to wrap the information to send to the message queue.
    The only required fields are type, id and timestamp. The rest of the fields are optional.
    """

    def __init__(self, type: str, id: str, timestamp: str, **kwargs):
        self.data = {"type": type, "id": id, "timestamp": timestamp, **kwargs}

    def __str__(self):
        return str(self.data)


class BaseSource(ABC, Thread, StreamingClient):
    """Base class for all sources.

    This class is used to provide a common interface for all sources. It
    provides a method to get the source name and a method to get the source data.

    """

    def __init__(self, sink: Queue, verbose: bool = False, **kwargs):
        Thread.__init__(self)
        load_dotenv()
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)
        self.bearer_token = os.getenv("BEARER_TOKEN")
        StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        if not sink:
            raise ValueError("The sink cannot be None.")
        self.sink = sink
        self._cleanup()  # Do a pre-cleanup.
        atexit.register(self._cleanup)

    def __str__(self):
        return self.__class__.__name__

    @abstractmethod
    def _cleanup(self):
        """Clean up the source."""

    def _send_data(self, information: Information):
        """This function is used to send the grabbed data to the message queue.
        It is supposed to be called within the callback function of the streaming
        function or in the forever loop.

        Args:
            information (Information): The data to send.
        """
        self.sink.put(information)

    @abstractmethod
    def run(self):
        """This method should wrap the streaming logic or a forever loop."""
        raise NotImplementedError
