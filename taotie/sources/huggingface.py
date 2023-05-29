import asyncio
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from taotie.entity import Information
from taotie.message_queue import MessageQueue
from taotie.sources.base import BaseSource
from taotie.utils import *


class HuggingFaceLeaderboard(BaseSource):
    """Listen to HuggingFace events."""

    def __init__(self, sink: MessageQueue, verbose: bool = False, **kwargs):
        BaseSource.__init__(self, sink=sink, verbose=verbose, **kwargs)
        self.url = "https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard"
        self.check_interval = kwargs.get("check_interval", 3600 * 12)
        self.logger.info(f"HuggingFace event initialized.")

    async def _cleanup(self):
        pass

    async def run(self):
        while True:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Setup the webdriver
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service)

                # Navigate to the page
                driver.get(self.url)

                # Switch to the iframe
                iframe = await loop.run_in_executor(
                    executor, driver.find_element, By.TAG_NAME, "iframe"
                )
                await loop.run_in_executor(executor, driver.switch_to.frame, iframe)

                # Get the content of the iframe
                iframe_content = driver.page_source

                # Use BeautifulSoup to parse the iframe content
                soup = BeautifulSoup(iframe_content, "html.parser")
                model_rows = soup.find_all("tr", {"class": "svelte-8hrj8a"})
                print(len(model_rows))

                for idx, row in enumerate(model_rows):
                    if idx > 10:
                        break
                    td_cells = row.find_all("td", {"class": "svelte-8hrj8a"})
                    if not td_cells:  # Skip header row
                        continue
                    # The first cell contains the model name and URL
                    model_cell = td_cells[0]
                    link_html = model_cell.find("a")
                    if not link_html or not link_html.text:
                        continue
                    model_name = model_cell.find("a").text.strip()
                    model_url = model_cell.find("a")["href"]
                    if not model_name or not model_url:
                        continue
                    # Check duplication and skip.

                    # Fetch the content via the url, using the huggingface_hub API.
                    model_readme_url = (
                        f"https://huggingface.co/{model_name}/raw/main/README.md"
                    )
                    content = (
                        f"{model_name} currently ranked at position {idx + 1} in the huggingface leaderboard. \n\n"
                        + fetch_url_content(model_readme_url)[:2000]
                    )

                    # Construct the information object.
                    huggingface_event = Information(
                        type="huggingface-model",
                        datetime_str=get_datetime(),
                        id=model_name,
                        uri=model_url,
                        content=content,
                    )
                    res = await self._send_data(huggingface_event)
                    if res:
                        self.logger.debug(f"{idx}: {huggingface_event.encode()}")
                    await asyncio.sleep(10)

                # Cleanup
                await loop.run_in_executor(executor, driver.quit)

                self.logger.info(
                    f"HuggingFace event checked. Will check again in {self.check_interval} seconds."
                )
                await asyncio.sleep(self.check_interval)


# async def run():
#     source = HuggingFaceLeaderboard(None, True)
#     await source.run()


# if __name__ == "__main__":
#     asyncio.run(run())
