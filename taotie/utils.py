# -*- coding: utf-8 -*-
import asyncio
import inspect
import json
import logging
import os
import random
import ssl
import sys
import tempfile
import threading
from asyncio import Lock
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import openai
import pytz  # type: ignore
import requests  # type: ignore
import retrying
from colorama import Fore, ansi
from dotenv import load_dotenv
from rdflib import Graph, Namespace


def load_env(env_file_path: str = "") -> None:
    if env_file_path:
        load_env(env_file_path)
    else:
        load_dotenv()


def get_datetime(timestamp: Optional[float] = None) -> str:
    """Convert the timestamp to datetime string.

    Args:
        timestamp (float): The timestamp to convert.

    Returns:
        str: The datetime string.
    """
    timezone = pytz.timezone("Etc/GMT+8")
    if not timestamp:
        timestamp = datetime.now().timestamp()
    return datetime.fromtimestamp(timestamp, timezone).strftime("%Y-%m-%d %H:%M:%S")


def fetch_url_content(url: str):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text.strip()
    else:
        raise Exception(
            f"Failed to fetch Markdown content from {url}, status code: {response.status_code}"
        )


def parse_json(json_str: str):
    return json.loads(json_str)


@retrying.retry(wait_fixed=10000, stop_max_attempt_number=3)
def chat_completion(
    model_type: str,
    prompt: str,
    content: str,
    max_tokens: int,
    temperature: float = 0.0,
):
    response = openai.ChatCompletion.create(
        model=model_type,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {"role": "user", "content": content},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response


# Create a logger class that accept level setting.
# The logger should be able to log to stdout and display the datetime, caller, and line of code.
class Logger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, logger_name: str, verbose: bool = True, level: Any = logging.INFO
    ):
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(logger_name)
            self.verbose = verbose
            self.logger.setLevel(level=level)
            self.formatter = logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s (%(filename)s:%(lineno)d)"
            )
            self.console_handler = logging.StreamHandler()
            self.console_handler.setLevel(level=level)
            self.console_handler.setFormatter(self.formatter)
            self.logger.addHandler(self.console_handler)

    def output(self, message: str, color: str = ansi.Fore.GREEN) -> None:
        print(color + message + Fore.RESET)

    def debug(self, message: str) -> None:
        if not self.verbose:
            return
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame[3]
        caller_line = caller_frame[2]
        self.logger.debug(
            Fore.MAGENTA + f"({caller_name} L{caller_line}): {message}" + Fore.RESET
        )

    def info(self, message: str) -> None:
        if not self.verbose:
            return
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame[3]
        caller_line = caller_frame[2]
        self.logger.info(
            Fore.BLACK + f"({caller_name} L{caller_line}): {message}" + Fore.RESET
        )

    def error(self, message: str) -> None:
        if not self.verbose:
            return
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame[3]
        caller_line = caller_frame[2]
        self.logger.error(
            Fore.RED + f"({caller_name} L{caller_line}): {message}" + Fore.RESET
        )

    def warning(self, message: str) -> None:
        if not self.verbose:
            return
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame[3]
        caller_line = caller_frame[2]
        self.logger.warning(
            Fore.YELLOW + f"({caller_name} L{caller_line}): {message}" + Fore.RESET
        )


async def text_to_triplets(
    text_summary: str,
    metadata: Dict[str, Any],
    logger: Logger,
    model_type: str = "gpt-3.5-turbo-16k-0613",
    max_tokens: int = 6000,
) -> List[str]:
    """Leverage prompt to use LLM to convert text summary to RDF triplets."""
    metadata_str = "\n".join(f"{key}: {value}" for key, value in metadata.items())
    metadata_str = metadata_str[:500]
    text_summary = text_summary[:1500]
    content = f"""
    {text_summary}
    {metadata_str}
    """
    content_type = "generic"
    if "type" in metadata:
        content_type = metadata["type"]

    if content_type == "arxiv":
        logger.info("Use arxiv prompt.")
        prompt = f"""
        Please convert the following information about a paper into triplets with the format "'subject' 'attribute' 'object'"? We want to follow the following rules:
        1. We need to WRAP EVERY part in the triplet with the SINGLE quotes, e.g. 'paper_title' 'has-author' 'John Dorr'.
        2. We want to use the paper title as the main entity.
        3. We want to include the triplets of the FIRST 2 authors and the LAST author, and link them to the paper title, e.g. '[paper_title]' 'has-author' '[Firstname Lastname]'.
        4. Create triplets about the afflication of these authors, e.g. '[Firstname Lastname]' 'has-affiliation' '[affiliation]'.
        5. Please represent the CORE concepts as triplets that you think is valuable to store in the knowledge graph. \
            Add AT LEAST 3 and AT MOST 8 tags with common words based on what the abstract described. For example, deep-learning, computer-vision, \
            nlp, multi-modality. etc. For each tag triplet, use the format  '[paper_title]' 'has-concept' '[tag]'.
        6. Please return a JSON where THERE IS A KEY "triplets" with a list of RDF triplets strings. \
            The JSON response will be DIRECTLY feed to a downstream program to parse the json.

        """
    elif content_type == "github-repo":
        logger.info("Use github-repo prompt.")
        prompt = f"""
        Please convert the following information about a github repository into triplets with the format "'subject' 'attribute' 'object'" \
            We want to follow the following rules:
        1. We need to WRAP EVERY part in the triplet with the SINGLE quotes, e.g. '[repo_name]' 'has-author' 'John Dorr'.
        2. We want to use the repo name as the main entity.
        3. IF there is any information about the language, we would want to include a triplet, '[repo_name]' 'implemented-in' '[language]'.
        4. Please represent the CORE concepts as triplets that you think is valuable to store in the knowledge graph. \
            Add AT LEAST 3 and AT MOST 8 tags with common words based on what the abstract described. For example, deep-learning, computer-vision, \
        5. Please return a JSON where THERE IS A KEY "triplets" with a list of RDF triplets strings. \
            The JSON response will be DIRECTLY feed to a downstream program to parse the json.
        """
    else:  # generic prompt to generate the triplets
        logger.info("Use generic prompt.")
        prompt = f"""
        Please convert the following information into triplets with the format "'subject' 'attribute' 'object'"? \
            We want to follow the following rules:
        1. We need to WRAP EVERY part in the triplet with the SINGLE quotes, e.g. 'paper_title' 'has-author' 'John Dorr'.
        2. We want to find out the title and use it as the main entity.
        3. We want to include the triplets of the FIRST 2 authors and the LAST author, and link them to the paper title, e.g. '[paper_title]' 'has-author' '[Firstname Lastname]'.
        4. If there is information about the affinitation, create triplets about the afflication of these authors, e.g. '[Firstname Lastname]' 'has-affiliation' '[affiliation]'.
        5. Please represent the CORE concepts as triplets that you think is valuable to store in the knowledge graph. \
            Add AT LEAST 3 and AT MOST 8 tags with common words based on what the abstract described. For example, deep-learning, computer-vision, \
        6. Please return a JSON where THERE IS A KEY "triplets" with a list of RDF triplets strings. \
        The JSON response will be DIRECTLY feed to a downstream program to parse the json.
        """

    # Call OpenAPI gpt-3.5-turbo-16k-0613 with the openai API
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY in .env.")
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = chat_completion(
        model_type=model_type,
        prompt=prompt,
        content=content,
        max_tokens=max_tokens,
        temperature=0.0,
    )
    result = response.choices[0].message.content
    json_blob = json.loads(result)
    rdf_triplets = json_blob.get("triplets", [])
    # LLM may generate each triplets as a list instead of a string.
    processed_triplets = []
    for triplet in rdf_triplets:
        if isinstance(triplet, list):
            triplet = " ".join(triplet[:3])
        processed_triplets.append(triplet)
    if logger:
        logger.output(f"RDF triplets: {rdf_triplets}\n", color=Fore.BLUE)
    return processed_triplets


def construct_knowledge_graph(triplets, logger: Optional[Logger] = None):
    if not logger:
        logger = Logger(os.path.basename(__file__))

    is_docker = os.getenv("IS_DOCKER", False)
    platform = "mac" if sys.platform.startswith("darwin") else "linux"
    # Create a Graph and a namespace
    knowledge_graph = Graph()
    n = Namespace("")
    # Create triplets
    for t in triplets:
        separator = " " if "' '" not in t else "' '"
        try:
            subj, pred, obj = t.split(separator)
            subj, pred, obj = (
                subj.replace("'", ""),
                pred.replace("'", ""),
                obj.replace("'", ""),
            )
            knowledge_graph.add((n[subj], n[pred], n[obj]))
        except Exception:
            logger.warning(f"Failed to parse triplet: {t}, skip this one.")
            continue

    # Create a Networkx Graph and visualize it
    graph = nx.DiGraph()
    for subj, pred, obj in knowledge_graph:
        graph.add_edge(str(subj), str(obj), label=str(pred.split("/")[-1]))

    # Configure the font
    plt.rcParams["font.family"] = "STKaiti"
    plt.rcParams[
        "axes.unicode_minus"
    ] = False  # to solve the problem of minus sign '-' shows as a square

    pos = nx.spring_layout(graph, k=100)
    node_labels = {n: n for n in graph.nodes}
    edge_labels = {(u, v): d["label"] for u, v, d in graph.edges(data=True)}
    font_size = 8
    # Draw the Networkx Graph
    nx.draw_networkx_edge_labels(
        graph,
        pos,
        edge_labels=edge_labels,
        font_size=font_size,
    )
    nx.draw_networkx_labels(
        graph,
        pos,
        labels=node_labels,
        font_size=font_size,
        font_color="red",
        verticalalignment="center",
    )

    nx.draw(
        graph,
        pos,
        with_labels=False,
        font_size=font_size,
        node_color="none",
        node_shape="s",
    )
    # Save the image to a file
    rnd = random.randint(0, 1000000)
    knowledge_graph_image_path = f"knowledge_graph_{rnd}.png"
    if is_docker:
        knowledge_graph_image_path = (
            f"/app/images/knowledge_graph/{knowledge_graph_image_path}"
        )
        if not os.path.exists("/app/images/knowledge_graph/"):
            os.makedirs("/app/images/knowledge_graph/")
    plt.savefig(knowledge_graph_image_path)
    plt.clf()
    logger.info(f"Knowledge graph image saved to {knowledge_graph_image_path}")
    # Return the file path
    return knowledge_graph_image_path


async def async_construct_knowledge_graph(triplets, logger: Optional[Logger] = None):
    if not logger:
        logger = Logger(os.path.basename(__file__))

    lock = Lock()
    async with lock:
        knowledge_graph_image_path = await asyncio.to_thread(
            construct_knowledge_graph, triplets, logger
        )
    return knowledge_graph_image_path


def check_url_exists(url):
    try:
        response = requests.head(url)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


async def extract_representative_image(
    repo_name: str, readme_url: str, logger: Logger
) -> str:
    # 1. Fetch the README.md content.
    content = ""
    try:
        readme_response = requests.get(readme_url)
        readme_response.raise_for_status()  # Raise an exception if the request was not successful
        content = readme_response.text[:6000]
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving content from URL: {e}")
    if not content:
        logger.warning(f"No README.md found via the path {readme_url}.")
        return ""
    # 2. Extract representative image.
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    content = f"""
        ```
        repo_name: {repo_name}
        {content}
        ```
        """
    logger.info(f"Extracting representative image from {repo_name}.")
    response = chat_completion(
        "gpt-3.5-turbo-16k-0613",
        prompt=f"""
        You are an information extractor that is going to extract the representative images according
        to the content of the markdown file given in the triple quotes. Please strictly follow the requirement, ONE by ONE:

        1. Please extract the link of the most representative image in the markdown content based on your inference.

        2. If the image path is already a full URL (e.g. starts with http:// or https://), use the URL as is.

        3. If the image path is a relative path, please construct the absolute path of the image with the rule:
        https://github.com[repo_name]/blob/[branch_name]/[relative_path].

        4. Please ONLY RETURN a JSON where THERE IS A KEY "image_url" with the link of the image, e.g.
        {{
            "image_url": "https://github.com/openai/openai-gpt/blob/main/image.png"
        }}

        6. Please DO NOT RETURN any other words OTHER THAN THE JSON ITSELF.
        """,
        content=content,
        max_tokens=2000,
    )
    image_url_json_str = response.choices[0].message.content
    # 3. Parse to get the url string.
    try:
        image_json_obj = json.loads(image_url_json_str)
        representative_image_url = image_json_obj.get("image_url", "")
        logger.info(f"Extracted representative image URL: {representative_image_url}.")
    except Exception as e:
        logger.error(
            f"Failed to extract representative image from {repo_name}. The image json string: [[{image_url_json_str}]]"
        )
        return ""
    try:
        valid = check_url_exists(representative_image_url)
        if not valid:
            logger.warning(
                f"No valid URL extracted as the representative image url for the repo {repo_name}."
            )
            return ""
        logger.info(
            f"Successfully extracted representative image {representative_image_url} from {repo_name}."
        )
    except Exception as e:
        logger.error(
            f"Failed to extract representative image from {repo_name}. The extracted URL is {representative_image_url}."
        )
        return ""
    # 4. Downlaod and then upload to imgur.
    return await save_image_to_imgur(representative_image_url, logger)


@retrying.retry(wait_fixed=10000, stop_max_attempt_number=3)
async def upload_image_to_imgur(image_path: str, logger: Logger) -> str:
    client_id = os.getenv("IMGUR_CLIENT_ID")
    if not client_id:
        raise ValueError("IMGUR_CLIENT_ID is not set")
    url = "https://api.imgur.com/3/image"
    headers = {"Authorization": f"Client-ID {client_id}"}

    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url, headers=headers, data={"image": image_data}, ssl=ssl_context
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except Exception as e:
            retest_interval = 300
            logger.warning(
                f"Failed to upload image to imgur: {e}, retest in {retest_interval} seconds."
            )
            await asyncio.sleep(retest_interval)
            return ""

    return data["data"]["link"]


# @retrying.retry(wait_fixed=10000, stop_max_attempt_number=3)
async def save_image_to_imgur(image_url: str, logger: Logger):
    # Get the image data
    if image_url.startswith("https://github.com/"):
        image_url = image_url.replace("blob", "raw")
    response = requests.get(image_url)
    response.raise_for_status()
    # Create a temporary file and save the image data
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(response.content)
        temp_file_path = temp.name
    logger.info(f"Download file to {temp_file_path}.")
    imgur_url = await upload_image_to_imgur(temp_file_path, logger)
    os.remove(temp_file_path)
    return imgur_url
