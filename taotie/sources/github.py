import asyncio

import aiohttp
from bs4 import BeautifulSoup

from taotie.entity import Information
from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource
from taotie.utils import *


class GithubTrends(BaseSource):
    """Listen to Github events.

    Args:
        username (str): Github username.
        repo (str): Github repo.
        event (str): Github event.
    """

    def __init__(self, sink: MessageQueue, verbose: bool = False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.url = "https://github.com/trending?since=daily.json"
        self.check_interval = kwargs.get("check_interval", 3600 * 12)
        self.readme_truncate_size = kwargs.get("readme_truncate_size", 2000)
        self.logger.info(f"Github event initialized.")

    async def _cleanup(self):
        pass

    async def run(self):
        """
        This method runs the GithubTrends source.

        It does the following:

        - Gets trending repositories from Github using get_trending_repos()
        - Processes each repository using process_repo() to extract information and generate a Github event
        - Sends the Github event to the sink using _send_data()
        - Sleeps for 10 seconds between processing repositories
        - Logs that the Github event was checked and will check again in self.check_interval seconds
        - Sleeps for self.check_interval seconds before repeating

        Args:
            session (aiohttp.ClientSession): The aiohttp ClientSession used to make requests

        Returns:
            None
        """
        async with aiohttp.ClientSession() as session:
            while True:
                repos = await self.get_trending_repos(session)
                for repo in repos:
                    github_event = await self.process_repo(session, repo)
                    res = await self._send_data(github_event)
                    if res:
                        self.logger.debug(f"{idx}: {github_event.encode()}")
                    await asyncio.sleep(10)
                self.logger.info(
                    f"Github event checked. Will check again in {self.check_interval} seconds."
                )
                await asyncio.sleep(self.check_interval)

    async def get_trending_repos(self, session):
        """
        Gets trending repositories from Github.

        Args:
            session (aiohttp.ClientSession): The aiohttp ClientSession used to make requests

        Returns:
            repo_blob (list): A list of BeautifulSoup elements representing trending repositories.
        """

        async with session.get(self.url, verify_ssl=False) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")
        repo_blob = soup.find_all("article", {"class": "Box-row"})
        return repo_blob

    async def process_repo(self, session, repo_blob):
        """
        Gets information from a Github repository and returns a Github event.

        Args:
            session (aiohttp.ClientSession): The aiohttp ClientSession used to make requests
            repo_blob (BeautifulSoup element): A BeautifulSoup element representing a trending Github repository

        Returns:
            github_event (Information): An Information object representing the Github event
        """

        repo_name = repo_blob.find("h2", {"class": "h3 lh-condensed"}).a["href"]
        # Extract other repo info...
        readme = await self.get_readme(session, repo_name)
        github_event = Information(
            type="github-repo",
            datetime_str=get_datetime(),
            id=repo_name,
            uri=repo_url,
            content=readme,
            # Other fields...
        )
        return github_event

    async def get_readme(self, session, repo_name):
        """
        Fetches the README.md file from a Github repository.

        Args:
            session (aiohttp.ClientSession): The aiohttp ClientSession used to make requests
            repo_name (str): The name of the Github repository

        Returns:
            readme (str): The content of the README.md file

        Raises:
            Exception: If the request fails with a status other than 200.
        """
        readme_url = f"https://raw.githubusercontent.com{repo_name}/master/README.md"
        async with session.get(readme_url, verify_ssl=False) as response:
            if response.status == 200:
                return await response.text()
            else:
                self.logger.warning(
                    f"Failed to fetch from {readme_url}. Status: {response.status}"
                )
                raise Exception(response.status)
