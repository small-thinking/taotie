"""A web service that accept the http request to collect the data.
"""

import asyncio

import aiohttp
from quart import Quart, jsonify, request
from unstructured.partition.html import partition_html  # type: ignore

from taotie.message_queue import MessageQueue, SimpleMessageQueue
from taotie.sources.base import BaseSource, Information
from taotie.utils import get_datetime


class HttpService(BaseSource):
    """A web service that accept the http request to collect the data."""

    def __init__(self, sink: MessageQueue, verbose=False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
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
        result = await self._process(url)
        return jsonify({"result": result})

    async def _process(self, url: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as response:
                    content_type = response.headers.get("Content-Type", "")
                    content = await response.text()
                    doc = None
                    if "text/html" in content_type:
                        elements = partition_html(text=content)
                        message = "\n".join([str(e) for e in elements])
                        doc = Information(
                            type="html",
                            datetime_str=get_datetime(),
                            id=url,
                            content=message[: self.truncate_size],
                        )
                    elif "application/pdf" in content_type:
                        message = "pdf"
                    else:
                        return "unknown"
                    if doc:
                        self.logger.info(doc)
                        # await self._send_data(doc)
                    return "ok"
        except Exception as e:
            return "error"

    async def run(self):
        self.app.run(host="0.0.0.0", port=6543)

    async def _cleanup(self):
        pass


if __name__ == "__main__":
    message_queue = SimpleMessageQueue()
    http_service = HttpService(sink=message_queue, verbose=True)
    asyncio.run(http_service.run())
