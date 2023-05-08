"""Base knowledge reporter.
Knowledge reporter is a separate service to conduct the post processing of the gathered knowledge.
"""

import asyncio
import atexit
import os
from abc import ABC, abstractmethod

from taotie.utils import *


class BaseReporter(ABC):
    """Base knowledge reporter."""

    def __init__(
        self,
        knowledge_source_uri: str,
        verbose: bool = False,
    ):
        """Initialize the knowledge reporter."""
        load_dotenv()
        self.knowledge_source_uri = knowledge_source_uri
        self.verbose = verbose
        self.logger = Logger(os.path.basename(__file__), verbose=verbose)
        atexit.register(self.cleanup)
        self._connected = False

    async def _connect(self):
        """Connect to the knowledge source if needed."""
        pass

    def cleanup(self):
        """Clean up the knowledge source."""
        asyncio.run(self._cleanup())

    @abstractmethod
    async def _cleanup(self):
        """Clean up the source."""
        pass

    async def distill(self):
        """Distill the knowledge."""
        if self._connected is False:
            await self._connect()
            self._connected = True
        await self._distill()

    @abstractmethod
    async def _distill(self):
        raise NotImplementedError
