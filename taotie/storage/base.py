"""Storage is used to dump the raw data or post-processed data into a persistent storage.
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from taotie.utils import Logger, load_dotenv


class Storage(ABC):
    def __init__(self, verbose: bool = False, **kwargs):
        self.verbose = verbose
        load_dotenv()
        self.logger = Logger(os.path.basename(__file__), verbose=verbose)

    @abstractmethod
    async def save(
        self, data: List[Tuple[Dict[str, Any], Dict[str, Any]]], image_urls: List[str]
    ):
        """Save the data to the storage."""
        raise NotImplementedError
