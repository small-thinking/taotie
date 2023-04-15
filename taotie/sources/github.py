import time
from queue import Queue

import requests
from bs4 import BeautifulSoup

from taotie.sources.base import BaseSource, Information


class GithubEvent(BaseSource):
    """Listen to Github events.

    Args:
        username (str): Github username.
        repo (str): Github repo.
        event (str): Github event.
    """

    def __init__(self, sink: Queue, verbose: bool = False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.url = "https://github.com/trending?since=daily.json"
        self.logger.info(f"Github event initialized.")

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
                github_event = Information(
                    type="github-repo",
                    timestamp=time.time(),
                    id=repo_name,
                    repo_url=repo_url,
                    repo_desc=repo_desc,
                    repo_lang=repo_lang,
                    repo_star=repo_star,
                    repo_fork=repo_fork,
                )
                self._send_data(github_event)
                self.logger.debug(f"{idx}: {github_event}")
            time.sleep(60)


# github = GithubEvent()
# github.run()
