import asyncio
import json
import os
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

from taotie.entity import Information
from taotie.message_queue import MessageQueue, SimpleMessageQueue
from taotie.sources.base import BaseSource
from taotie.utils.utils import get_datetime


class Arxiv(BaseSource):
    """Listen to Arxiv papers.

    Args:
        authors (list): List of author names.
    """

    def __init__(self, sink: MessageQueue, verbose: bool = False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.arxiv_author_json_file = kwargs.get(
            "arxiv_author_json", "arxiv_author.json"
        )
        # Load authors as a dict of affiliation: [authors]
        self.logger.info(
            f"Loading arxiv author data from [{self.arxiv_author_json_file}]"
        )
        self.authors = []
        with open(self.arxiv_author_json_file) as f:
            author_dict = json.load(f)
        self.authors = [
            author for affiliation in author_dict for author in author_dict[affiliation]
        ]
        self.days_lookback = int(kwargs.get("days_lookback", "90"))
        self.check_interval = kwargs.get("check_interval", 3600 * 3)
        self.logger.info(f"Arxiv data source initialized.")

    async def _cleanup(self):
        pass

    async def run(self):
        async with aiohttp.ClientSession() as session:
            while True:
                for idx, author in enumerate(self.authors):
                    self.logger.info(
                        f"[{idx}/{len(self.authors)}] Check the published paper by the author [{author}]."
                    )
                    author_str = "%20".join(author.split(" "))
                    url = f'http://export.arxiv.org/api/query?search_query=au:"{author_str}"&max_results=2&sortBy=submittedDate&sortOrder=descending'
                    try:
                        async with session.get(url) as response:
                            soup = BeautifulSoup(await response.text(), "xml")
                    except aiohttp.client_exceptions.ServerDisconnectedError:
                        self.logger.error(
                            f"ArxivSource disconnected. Probably hit rate limit. Retry in 1 min."
                        )
                        await asyncio.sleep(60)
                        async with session.get(url) as response:
                            soup = BeautifulSoup(await response.text(), "xml")

                    entries = soup.find_all("entry")
                    for entry in entries:
                        uri = entry.id.text
                        title = entry.title.text.replace("\n", "")
                        abstract = entry.summary.text
                        paper_published = entry.published.text
                        paper_updated = entry.updated.text
                        # Skip this paper if it's too old
                        if datetime.now() - datetime.strptime(
                            paper_published, "%Y-%m-%dT%H:%M:%SZ"
                        ) > timedelta(days=self.days_lookback):
                            continue

                        authors = ", ".join(
                            [author.text.strip() for author in soup.find_all("author")]
                        )

                        paper_info = Information(
                            type="arxiv",
                            datetime_str=get_datetime(),
                            id=title,
                            uri=uri,
                            content=f"Title: {title}\n\nAuthors: {authors}\n\nAbstract: {abstract}",
                            paper_published=paper_published,
                            paper_updated=paper_updated,
                        )
                        await self._send_data(paper_info)
                        if self.verbose:
                            self.logger.info(f"{title}: {paper_info.encode()}")
                        await asyncio.sleep(20)
                self.logger.info(
                    f"ArxivSource checked. Will check again in {self.check_interval} seconds."
                )
                await asyncio.sleep(self.check_interval)


if __name__ == "__main__":
    message_queue = SimpleMessageQueue()
    http_service = Arxiv(sink=message_queue, verbose=True)
    asyncio.run(http_service.run())
