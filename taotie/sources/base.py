import atexit
import json
import os
from abc import ABC, abstractmethod
from threading import Thread
from typing import Any, Dict

from taotie.message_queue import MessageQueue
from taotie.utils import *


class Information:
    """This class is used to wrap the information to send to the message queue.
    The only required fields are type, id and timestamp. The rest of the fields are optional.
    """

    def __init__(self, type: str, id: str, datetime_str: str, **kwargs):
        self.data: Dict[str, Any] = {
            "type": type,
            "id": id,
            "datetime": datetime_str,
            **kwargs,
        }

    def __repr__(self):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

    def encode(self):
        return json.dumps(self.data, ensure_ascii=False)


class BaseSource(ABC, Thread):
    """Base class for all sources.

    This class is used to provide a common interface for all sources. It
    provides a method to get the source name and a method to get the source data.

    """

    def __init__(self, sink: MessageQueue, verbose: bool = False, **kwargs):
        Thread.__init__(self)
        load_dotenv()
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)
        # self.bearer_token = os.getenv("BEARER_TOKEN")
        # StreamingClient.__init__(self, bearer_token=self.bearer_token, **kwargs)
        if not sink:
            raise ValueError("The sink cannot be None.")
        self.sink = sink
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
        self.sink.put(information.encode())

    @abstractmethod
    def run(self):
        """This method should wrap the streaming logic or a forever loop."""
        raise NotImplementedError
