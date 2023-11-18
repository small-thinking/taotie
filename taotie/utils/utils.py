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
import pytz  # type: ignore
import requests  # type: ignore
import retrying
from colorama import Fore, ansi
from dotenv import load_dotenv
from flask import jsonify
from openai import OpenAI


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
    response_format: Any = {"type": "text"},
    temperature: float = 0.0,
    client: Optional[OpenAI] = None,
) -> str:
    if client is None:
        client = OpenAI(
            # defaults to os.environ.get("OPENAI_API_KEY")
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    response = client.chat.completions.create(
        model=model_type,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {"role": "user", "content": content},
        ],
        max_tokens=min(4000, max_tokens),
        response_format=response_format,
        temperature=temperature,
    )
    print(response)
    # refactor the below line by checking the response.choices[0].message.content step by step, and handle the error.
    if not response.choices or len(response.choices) == 0:
        raise Exception(
            f"Failed to parse choices from openai.ChatCompletion response. The response: {response}"
        )
    first_choice = response.choices[0]
    if not first_choice.message:
        raise Exception(
            f"Failed to parse message from openai.ChatCompletion response. The choices block: {first_choice}"
        )
    message = first_choice.message
    if not message.content:
        raise Exception(
            f"Failed to parse content openai.ChatCompletion response. The message block: {message}"
        )
    result = message.content
    return result


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
    logger: Optional[Logger] = None,
    model_type: str = "gpt-3.5-turbo-1106",
    max_tokens: int = 4000,
    client: Optional[OpenAI] = None,
):
    if not logger:
        logger = Logger(os.path.basename(__file__))
    load_env()
    # Call OpenAPI gpt-3.5-turbo-1106 with the openai API
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY in .env.")
    if not client:
        client = OpenAI(
            # defaults to os.environ.get("OPENAI_API_KEY")
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if not text_summary:
        return jsonify({"error": "No input provided"}), 400

    metadata_str = "\n".join(f"{key}: {value}" for key, value in metadata.items())
    metadata_str = metadata_str[:500]
    text_summary = text_summary[:1500]

    function_description = """
    Generate a knowledge graph with entities and relationships.
    Use the colors to help differentiate between different node or edge types/categories.
    Please use light color for the nodes so the label can be clearly visible.
    """
    # Always provide light pastel colors that work well with black font.
    succeeded = False
    while not succeeded:
        completion = client.chat.completions.create(
            model=model_type,
            max_tokens=min(4000, max_tokens),
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Please generate a brief yet comprehensive knowledge graph in json format with the information.",
                },
                {
                    "role": "user",
                    "content": f"""
                        {text_summary}
                        {metadata_str}
                    """,
                },
            ],
            functions=[
                {
                    "name": "knowledge_graph",
                    "description": function_description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "createdDate": {"type": "string"},
                                    "lastUpdated": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                            "nodes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "label": {"type": "string"},
                                        "type": {"type": "string"},
                                        "color": {
                                            "type": "string"
                                        },  # Added color property
                                        "properties": {
                                            "type": "object",
                                            "description": "Additional attributes for the node",
                                        },
                                    },
                                    "required": [
                                        "id",
                                        "label",
                                        "type",
                                        "color",
                                    ],  # Added color to required
                                },
                            },
                            "edges": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from": {"type": "string"},
                                        "to": {"type": "string"},
                                        "relationship": {"type": "string"},
                                        "direction": {"type": "string"},
                                        "color": {
                                            "type": "string"
                                        },  # Added color property
                                        "properties": {
                                            "type": "object",
                                            "description": "Additional attributes for the edge",
                                        },
                                    },
                                    "required": [
                                        "from",
                                        "to",
                                        "relationship",
                                        "color",
                                    ],  # Added color to required
                                },
                            },
                        },
                        "required": ["nodes", "edges"],
                    },
                }
            ],
            function_call={"name": "knowledge_graph"},
        )
        function_call_obj = completion.choices[0].message.function_call
        if hasattr(function_call_obj, "arguments"):
            response_data = getattr(function_call_obj, "arguments")
        else:
            logger.error(f"No arguments from function call.")
            response_data = ""

        try:
            triplets = json.loads(response_data)
            succeeded = True
        except json.decoder.JSONDecodeError:
            print("error")

    return triplets


def construct_knowledge_graph(triplets, logger: Optional[Logger] = None) -> str:
    if not logger:
        logger = Logger(os.path.basename(__file__))

    is_docker = os.getenv("IS_DOCKER", False)

    G = nx.DiGraph()
    for node in triplets["nodes"]:
        G.add_node(node["id"], label=node["label"], color=node["color"])

    for edge in triplets["edges"]:
        G.add_edge(
            edge["from"], edge["to"], label=edge["relationship"], color=edge["color"]
        )

    # Configure the font for Unicode
    plt.rcParams["font.family"] = "Arial Unicode MS"
    plt.rcParams["axes.unicode_minus"] = False

    pos = nx.spring_layout(G, k=0.5, iterations=50)
    node_labels = {n: G.nodes[n]["label"] for n in G.nodes()}
    edge_labels = nx.get_edge_attributes(G, "label")

    nx.draw(
        G,
        pos,
        with_labels=False,
        node_color=[nx.get_node_attributes(G, "color")[n] for n in G.nodes()],
    )
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8, font_color="red")
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    rnd = random.randint(0, 1000000)
    knowledge_graph_image_path = f"knowledge_graph_{rnd}.png"
    if is_docker:
        knowledge_graph_image_path = (
            f"/app/images/knowledge_graph/{knowledge_graph_image_path}"
        )
        if not os.path.exists("/app/images/knowledge_graph/"):
            os.makedirs("/app/images/knowledge_graph/")

    plt.savefig(f"{knowledge_graph_image_path}")
    plt.clf()
    logger.info(f"Knowledge graph image saved to {knowledge_graph_image_path}")
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
    """Extracts the representative image from a GitHub repository README.md.

    Parameters:
    repo_name (str): The name of the GitHub repository.
    readme_url (str): The URL of the README.md file.
    logger (Logger): The logger object.

    Returns:
    str: The URL of the representative image uploaded to Imgur.

    Functionality:
    1. Fetches the README.md content from the given URL.
    2. Uses OpenAI's chat completion API to extract the most representative image URL from the README.md content.
    3. Checks if the extracted URL is valid. If not, returns an empty string.
    4. Downloads the image at the extracted URL and uploads it to Imgur.
    5. Returns the Imgur URL of the uploaded image. If any step fails, returns an empty string.
    """
    # 1. Fetch the README.md content.
    content = ""
    try:
        readme_response = requests.get(readme_url)
        readme_response.raise_for_status()  # Raise an exception if the request was not successful
        content = readme_response.text[:4000]
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving content from URL: {e}")
    if not content:
        logger.warning(f"No README.md found via the path {readme_url}.")
        return ""
    # 2. Extract representative image.
    load_dotenv()
    content = f"""
        ```
        repo_name: {repo_name}
        {content}
        ```
        """
    logger.info(f"Extracting representative image from {repo_name}.")
    image_url_json_str = chat_completion(
        "gpt-3.5-turbo-1106",
        prompt=f"""
        You are an information extractor that is going to extract the representative images according
        to the content of the markdown file given in the triple quotes. Please strictly follow the requirement, ONE by ONE:

        1. Please extract the link of the most representative image in the markdown content based on your inference.
        2. If the image path is already a full URL (e.g. starts with http:// or https://), use the URL as is.
        3. If the image path is a relative path, please construct the absolute path of the image with the rule:
        https://github.com[repo_name]/blob/[branch_name]/[relative_path].
        4. The image can be with extension .png, .jpg, .jpeg, .gif, etc.
        5. Please ONLY RETURN a JSON where THERE IS A KEY "image_url" with the link of the image, e.g.
        {{
            "image_url": "https://github.com/openai/openai-gpt/blob/main/image.png"
        }}
        6. Please DO NOT RETURN any other words OTHER THAN THE JSON ITSELF.
        """,
        content=content,
        response_format={"type": "json_object"},
        max_tokens=2000,
    )
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
