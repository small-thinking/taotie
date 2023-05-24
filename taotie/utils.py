import asyncio
import inspect
import json
import logging
import os
import random
import re
import ssl
import sys
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


def parse_json(json_str):
    try:
        # Try to parse the string with json.loads. If it's not malformed, it will succeed.
        return json.loads(json_str)
    except json.JSONDecodeError:
        # If it's malformed, add quotes around keys and values that don't have them.
        pattern = r"([\{\s,])([^:\{\}\[\]\s]+):"
        fixed_json = re.sub(pattern, r'\1"\2":', json_str)
        pattern = r': ([^"\{\}\[\]\s]+)([,\}\]])'
        fixed_json = re.sub(pattern, r': "\1"\2', fixed_json)
        return json.loads(fixed_json)


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
    model_type: str = "gpt-3.5-turbo",
    max_tokens: int = 2500,
) -> List[str]:
    """Leverage prompt to use LLM to convert text summary to RDF triplets."""
    metadata_str = "\n".join(f"{key}: {value}" for key, value in metadata.items())
    metadata_str = metadata_str[:2000]
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

    # Call OpenAPI gpt-3.5-turbo with the openai API
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
        subj, pred, obj = t.split(separator)
        subj, pred, obj = (
            subj.replace("'", ""),
            pred.replace("'", ""),
            obj.replace("'", ""),
        )
        knowledge_graph.add((n[subj], n[pred], n[obj]))

    # Create a Networkx Graph and visualize it
    graph = nx.DiGraph()
    for subj, pred, obj in knowledge_graph:
        graph.add_edge(str(subj), str(obj), label=str(pred.split("/")[-1]))
    # Draw the Networkx Graph
    pos = nx.spring_layout(graph, k=100)
    node_labels = {n: n for n in graph.nodes}
    edge_labels = {(u, v): d["label"] for u, v, d in graph.edges(data=True)}
    font_size = 8
    font_family = "Source Han Sans" if platform == "mac" else "Noto Sans CJK SC"

    nx.draw_networkx_edge_labels(
        graph,
        pos,
        edge_labels=edge_labels,
        font_size=font_size,
        font_family=font_family,
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
        font_family=font_family,
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


async def upload_image_to_imgur(image_path):
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
        async with session.post(
            url, headers=headers, data={"image": image_data}, ssl=ssl_context
        ) as response:
            response.raise_for_status()
            data = await response.json()

    return data["data"]["link"]
