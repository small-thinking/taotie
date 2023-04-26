"""A web service that accept the http request to collect the data.
"""
import asyncio

import aiohttp
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart, jsonify, request
from unstructured.partition.html import partition_html  # type: ignore

from taotie.entity import Information
from taotie.message_queue import MessageQueue, SimpleMessageQueue
from taotie.sources.base import BaseSource
from taotie.utils import get_datetime


class HttpService(BaseSource):
    """A web service that accept the http request to collect the data."""

    def __init__(self, sink: MessageQueue, verbose=False, **kwargs):
        super().__init__(sink=sink, verbose=verbose, **kwargs)
        self.app = Quart(__name__)
        self.app.add_url_rule(
            "/api/v1/url", "check_url", self.check_url, methods=["POST"]
        )
        self.truncate_size = kwargs.get("truncate_size", -1)
        self.logger.info("HttpService initialized.")

    async def check_url(self):
        data = await request.get_json()
        if "url" not in data:
            return jsonify({"error": "Missing URL parameter"}), 400
        url = data["url"]
        content_type = data.get("content_type", "")
        result = await self._process(url=url, content_type=content_type)
        return jsonify({"result": result})

    async def _process(self, url: str, content_type: str = "html") -> str:
        self.logger.info(f"HttpService received {url} and {content_type}.")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, allow_redirects=True, verify_ssl=False
                ) as response:
                    content = await response.text()
                    doc = None
                    if content_type in ["html", "github-repo"]:
                        elements = partition_html(text=content)
                        message = "\n".join([str(e) for e in elements])
                        doc = Information(
                            type=content_type,
                            datetime_str=get_datetime(),
                            id=url,
                            uri=url,
                            content=message[: self.truncate_size],
                        )
                    elif "application/pdf" in content_type:
                        message = "pdf"
                    else:
                        return f"unknown content type {content_type}."
                    if doc:
                        # self.logger.output(doc.encode())
                        await self._send_data(doc)
                    return "ok"
        except Exception as e:
            self.logger.error(f"Error: {e}")
            return "error"

    async def run(self):
        config = Config()
        config.bind = ["0.0.0.0:6543"]
        await serve(self.app, config)

    async def _cleanup(self):
        pass


if __name__ == "__main__":
    message_queue = SimpleMessageQueue()
    http_service = HttpService(sink=message_queue, verbose=True)
    asyncio.run(http_service.run())
