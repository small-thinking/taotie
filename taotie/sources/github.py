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

    async def _extract_repo_info(self, blob, session):
        repo_name = blob.find("h2", {"class": "h3 lh-condensed"}).a["href"]
        repo_url = (
            "https://github.com"
            + blob.find("h2", {"class": "h3 lh-condensed"}).a["href"]
        )
        repo_desc_blob = blob.find("p", {"class": "col-9 color-fg-muted my-1 pr-4"})
        repo_desc = repo_desc_blob.text.strip() if repo_desc_blob else ""
        repo_lang_blob = blob.find("span", {"class": "d-inline-block ml-0 mr-3"})
        repo_lang = repo_lang_blob.text.strip() if repo_lang_blob else ""
        star_and_fork = blob.find_all("a", {"class": "Link--muted d-inline-block mr-3"})
        repo_star = star_and_fork[0].text.strip()
        repo_fork = star_and_fork[1].text.strip()
        # Extract the detailed description from the github main README.md if any.
        readme_url = f"https://raw.githubusercontent.com{repo_name}/master/README.md"
        if not check_url_exists(readme_url):
            readme_url = f"https://raw.githubusercontent.com{repo_name}/main/README.md"
        repo_readme = ""
        try:
            async with session.get(readme_url, verify_ssl=False) as readme_response:
                if readme_response.status == 200:
                    repo_readme = await readme_response.text()
                    repo_readme = repo_readme[: self.readme_truncate_size]
                else:
                    self.logger.warning(
                        f"Failed to fetch from {readme_url}. Status: {readme_response.status}"
                    )
                    raise Exception(readme_response.status)
            return {
                "repo_name": repo_name,
                "repo_url": repo_url,
                "repo_desc": repo_desc,
                "repo_lang": repo_lang,
                "repo_star": repo_star,
                "repo_fork": repo_fork,
                "repo_readme": repo_readme,
            }
        except Exception as e:
            self.logger.warning(f"Failed to fetch from {readme_url}. Reason: {e}")
            return {}

    async def run(self):
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(self.url, verify_ssl=False) as response:
                    soup = BeautifulSoup(await response.text(), "html.parser")

                repo_blob = soup.find_all("article", {"class": "Box-row"})
                for idx, blob in enumerate(repo_blob):
                    repo_meta = await self._extract_repo_info(blob, session)
                    try:
                        github_event = Information(
                            type="github-repo",
                            datetime_str=get_datetime(),
                            id=repo_meta["repo_name"],
                            uri=repo_meta["repo_url"],
                            content=repo_meta["repo_readme"],
                            repo_desc=repo_meta["repo_desc"],
                            repo_lang=repo_meta["repo_lang"],
                            repo_star=repo_meta["repo_star"],
                            repo_fork=repo_meta["repo_fork"],
                        )
                    except:
                        self.logger.error(f"Repo meta: {repo_meta}")
                    res = await self._send_data(github_event)
                    if res:
                        self.logger.debug(f"{idx}: {github_event.encode()}")
                    await asyncio.sleep(10)
                self.logger.info(
                    f"Github event checked. Will check again in {self.check_interval} seconds."
                )
                await asyncio.sleep(self.check_interval)
