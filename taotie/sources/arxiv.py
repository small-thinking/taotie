import asyncio
import os
from datetime import datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

from taotie.entity import Information
from taotie.message_queue import MessageQueue, SimpleMessageQueue
from taotie.sources.base import BaseSource
from taotie.utils import get_datetime


class Arxiv(BaseSource):
    """Listen to Arxiv papers.

    Args:
        authors (list): List of author names.
    """

    def __init__(self, sink: MessageQueue, verbose: bool = False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.authors = os.environ.get("ARXIV_AUTHORS", "").split(",")
        self.days_lookback = int(kwargs.get("days_lookback", "90"))
        self.check_interval = kwargs.get("check_interval", 3600 * 12)
        self.logger.info(f"Arxiv data source initialized.")

    async def _cleanup(self):
        pass

    async def run(self):
        async with aiohttp.ClientSession() as session:
            while True:
                for author in self.authors:
                    author_str = "%20".join(author.split(" "))
                    url = f'http://export.arxiv.org/api/query?search_query=au:"{author_str}"&max_results=2&sortBy=submittedDate&sortOrder=descending'
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
                        await asyncio.sleep(10)
                self.logger.info(
                    f"ArxivSource checked. Will check again in {self.check_interval} seconds."
                )
                await asyncio.sleep(self.check_interval)


if __name__ == "__main__":
    message_queue = SimpleMessageQueue()
    http_service = Arxiv(sink=message_queue, verbose=True)
    asyncio.run(http_service.run())
