import time

import requests  # type: ignore
from bs4 import BeautifulSoup

from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource, Information
from taotie.utils import get_datetime


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
        self.logger.info(f"Github event initialized.")
        self.readme_truncate_size = kwargs.get("readme_truncate_size", 2000)

    def _cleanup(self):
        pass

    def run(self):
        while True:
            response = requests.get(self.url)
            soup = BeautifulSoup(response.text, "html.parser")

            repo_blob = soup.find_all("article", {"class": "Box-row"})
            for idx, blob in enumerate(repo_blob):
                repo_name = blob.find("h2", {"class": "h3 lh-condensed"}).a["href"]
                repo_url = (
                    "https://github.com"
                    + blob.find("h2", {"class": "h3 lh-condensed"}).a["href"]
                )
                repo_desc_blob = blob.find(
                    "p", {"class": "col-9 color-fg-muted my-1 pr-4"}
                )
                repo_desc = repo_desc_blob.text.strip() if repo_desc_blob else ""
                repo_lang_blob = blob.find(
                    "span", {"class": "d-inline-block ml-0 mr-3"}
                )
                repo_lang = repo_lang_blob.text.strip() if repo_lang_blob else ""
                star_and_fork = blob.find_all(
                    "a", {"class": "Link--muted d-inline-block mr-3"}
                )
                repo_star = star_and_fork[0].text.strip()
                repo_fork = star_and_fork[1].text.strip()
                # Extract the detailed description from the github main README.md if any.
                readme_url = (
                    f"https://raw.githubusercontent.com{repo_name}/master/README.md"
                )
                try:
                    readme_response = requests.get(readme_url)
                    if readme_response.status_code == 200:
                        repo_readme = readme_response.text[: self.readme_truncate_size]
                except Exception as e:
                    repo_readme = ""

                github_event = Information(
                    type="github-repo",
                    datetime_str=get_datetime(),
                    id=repo_name,
                    repo_url=repo_url,
                    repo_desc=repo_desc,
                    repo_readme=repo_readme,
                    repo_lang=repo_lang,
                    repo_star=repo_star,
                    repo_fork=repo_fork,
                )
                self._send_data(github_event)
                self.logger.debug(f"{idx}: {github_event.encode()}")
            time.sleep(60)
