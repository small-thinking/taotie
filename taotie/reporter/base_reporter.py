"""Base knowledge reporter.
Knowledge reporter is a separate service to conduct the post processing of the gathered knowledge.
"""

import asyncio
import atexit
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple

from taotie.storage.notion import NotionStorage
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

    async def distill(self, database_id: Optional[str] = None, **kwargs):
        """Distill the knowledge."""
        if self._connected is False:
            await self._connect()
            self._connected = True
        result = await self._distill()
        result_json = parse_json(result)
        if database_id:
            self.logger.info("Write reports to notion.")
            # Construct NotionStorage and the input and save the report into notion.
            storage = NotionStorage(root_page_id=None, verbose=self.verbose)
            current_date = datetime.now()
            formatted_date = current_date.strftime("%Y/%m/%d")
            language = kwargs.get("language", "Chinese")
            if language == "Chinese":
                type = "开源篇" if kwargs.get("type", None) == "github-repo" else "学术篇"
                title = "{formatted_date} AI进展报告{type}".format(
                    formatted_date=formatted_date, type=type
                )
            else:
                type = (
                    "Open Source"
                    if kwargs.get("type", None) == "github-repo"
                    else "Academia"
                )
                title = "{formatted_date} AI Progress Report -- {type}".format(
                    formatted_date=formatted_date, type=type
                )

            data: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
            data.append(
                (
                    {
                        "id": title,
                        "datetime": datetime.now().isoformat(),
                        "type": "report",
                        "tags": ["test1", "test2"],
                        "content": result_json,
                    },
                    {},
                )
            )
            image_files = []
            for entry in result_json["results"]:
                if "Image URLs" not in entry:
                    continue
                for image_url in entry["Image URLs"]:
                    image_files.append(image_url)
                    break  # only pick one image from each entry
            await storage.save(
                data, image_urls=image_files, database_id=database_id, doc_type="report"
            )

    @abstractmethod
    async def _distill(self) -> str:
        raise NotImplementedError
