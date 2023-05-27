import atexit
import os
from abc import ABC, abstractmethod

from taotie.entity import Information
from taotie.message_queue import MessageQueue
from taotie.storage.memory import DedupMemory
from taotie.utils import *


class BaseSource(ABC):
    """Base class for all sources.

    This class is used to provide a common interface for all sources. It
    provides a method to get the source name and a method to get the source data.

    """

    def __init__(
        self,
        sink: MessageQueue,
        verbose: bool = False,
        dedup_memory: Optional[DedupMemory] = None,
        **kwargs,
    ):
        load_dotenv()
        if not sink:
            raise ValueError("The sink cannot be None.")
        self.logger = Logger(logger_name=os.path.basename(__file__), verbose=verbose)
        self.verbose = (verbose,)
        self.sink = sink
        self.dedup_memory = dedup_memory
        atexit.register(self._cleanup)

    def __str__(self):
        return self.__class__.__name__

    @abstractmethod
    async def _cleanup(self):
        """Clean up the source."""

    async def _send_data(self, information: Information) -> bool:
        """This function is used to send the grabbed data to the message queue.
        It is supposed to be called within the callback function of the streaming
        function or in the forever loop.

        Args:
            information (Information): The data to send.

        Returns:
            bool: True if the data is sent successfully, False otherwise.
        """
        # Skip duplicate information according to the id.
        if self.dedup_memory:
            id = information.get_id()
            if await self.dedup_memory.exists(id):
                self.logger.warning(f"Duplicated information: {id}, will ignore.")
                return False
        await self.sink.put(information.encode())
        # Record the index.
        if self.dedup_memory:
            await self.dedup_memory.check_and_save(id)
        return True

    @abstractmethod
    async def run(self):
        """This method should wrap the streaming logic or a forever loop."""
        raise NotImplementedError
