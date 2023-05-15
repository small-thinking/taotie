"""A web service that accept the http request to collect the data.
"""
import asyncio
import traceback
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
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

                    if content_type == "github-repo":
                        doc = await self._parse_github_repo(url, content)
                    elif "arxiv.org/abs/" in url:
                        # Parse the arxiv link. Extract the title, abstract, authors, and link to the paper.
                        doc = await self._parse_arxiv(url, content)
                    elif "application/pdf" in content_type:
                        message = "pdf"
                    elif content_type in ["html", "blog"]:
                        elements = partition_html(text=content)
                        message = "\n".join([str(e) for e in elements])
                        doc = Information(
                            type=content_type,
                            datetime_str=get_datetime(),
                            id=url,
                            uri=url,
                            content=message[: self.truncate_size],
                        )
                    else:
                        return f"unknown content type {content_type}."
                    if doc:
                        self.logger.output(doc.encode())
                        await self._send_data(doc)
                    return "ok"
        except Exception as e:
            self.logger.error(f"Error: {e}")
            traceback.print_exc()
            return "error"

    async def run(self):
        config = Config()
        config.bind = ["0.0.0.0:6543"]
        await serve(self.app, config)

    async def _cleanup(self):
        pass

    async def _parse_github_repo(self, url: str, content: str) -> Information:
        elements = partition_html(text=content)
        message = "\n".join([str(e) for e in elements])
        # Only keep the last two sections of the github repo and use it for the id.
        parsed_url = urlparse(url)
        last_two_segments = parsed_url.path.split("/")[-2:]
        id = "/" + "/".join(last_two_segments)
        return Information(
            type="github-repo",
            datetime_str=get_datetime(),
            id=id,
            uri=url,
            content=message[: self.truncate_size],
        )

    async def _parse_arxiv(self, url: str, content: str) -> Information:
        """Parse the arxiv link. Extract the title, abstract, authors, and link to the paper."""
        soup = BeautifulSoup(content, "html.parser")

        title = (
            soup.find("h1", class_="title mathjax")
            .text.strip()
            .replace("Title:", "")
            .strip()
        )
        abstract = (
            soup.find("blockquote", class_="abstract mathjax")
            .text.strip()
            .replace("Abstract: ", "")
        )
        authors = ", ".join(
            [
                author.text.strip()
                for author in soup.find_all("div", class_="authors")[0].find_all("a")
            ]
        )
        pdf_link = (
            "https://arxiv.org"
            + soup.find("div", class_="full-text").find("a", class_="download-pdf")[
                "href"
            ]
        )

        doc = Information(
            type="arxiv",
            datetime_str=get_datetime(),
            id=title,
            uri=url,
            content=f"Title: {title}\n\nAuthors: {authors}\n\nAbstract: {abstract}",
        )

        return doc


if __name__ == "__main__":
    message_queue = SimpleMessageQueue()
    http_service = HttpService(sink=message_queue, verbose=True)
    asyncio.run(http_service.run())
