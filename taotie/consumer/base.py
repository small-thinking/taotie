"""Consumer the data collected by the gatherer.

"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from taotie.storage.base import Storage
from taotie.utils import Logger


class Consumer(ABC):
    """A concrete consumer would inherit from the Consumer class and implement the process method.
    The logic inside the process can be as simple as printing the message or as complex as an
    orchestrator such as a langchain application.
    """

    def __init__(
        self,
        verbose: bool = False,
        dedup: bool = False,
        storage: Optional[Storage] = None,
        **kwargs,
    ):
        """Initialize the consumer.

        Args:
            verbose (bool, optional): Whether to print the log. Defaults to False.
            dedup (bool, optional): Whether to deduplicate the messages by id. Defaults to False.
            **kwargs: Other arguments.
        """
        self.verbose = verbose
        self.logger = Logger(logger_name=__name__, verbose=verbose)
        self.dedup = dedup
        self.storage = storage
        if not self.storage:
            self.logger.warning("The storage is not set.")
        self.kwargs = kwargs
        self.in_memory_index: Dict[str, Dict[str, Any]] = {}

    async def process(self, messages: List[Dict[str, Any]]) -> None:
        """Process the message."""
        if self.dedup:
            messages = await self._dedup(messages)
        await self._process(messages)

    async def _dedup(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate the messages by id in memory."""
        deduped_messages = [m for m in messages if m["id"] not in self.in_memory_index]
        self.logger.info(f"Deduped: {len(messages) - len(deduped_messages)} messages.")
        self.in_memory_index.update({m["id"]: m for m in deduped_messages})
        return deduped_messages

    @abstractmethod
    async def _process(self, messages: List[Dict[str, Any]]) -> None:
        """Process the message."""
        raise NotImplementedError
