"""Test the utils.  
Run this test with command: pytest taotie/tests/test_utils.py"""
from unittest.mock import patch  

import pytest

from taotie.utils import *


@pytest.mark.parametrize(
    "input, expected",
    [(1681684094, "2023-04-16 14:28:14")],
)
def test_get_datetime(input, expected):
    assert get_datetime(input) == expected


def test_load_dotenv():
    with patch.dict("os.environ", {"TEST_KEY": "test value"}):
        load_dotenv()
        assert os.environ.get("TEST_KEY") == "test value"


def test_logger():
    logger = Logger("test_logger")
    assert logger.logger.name == "test_logger"


@pytest.mark.parametrize(
    "url, response_text, status_code, expected_output, expected_exception",
    [
        (
            "https://raw.githubusercontent.com/Open-EdTech/python-for-dev/main/README.md",
            "Python for Developers",
            200,
            "Python for Developers",
            None,
        ),  # Test with a valid URL
        (
            "https://example.com/404",
            "",
            404,
            None,
            Exception,
        ),  # Test with a 404 error
        (
            "https://example.com/notfound",
            "",
            500,
            None,
            Exception,
        ),  # Test with a 500 error
    ],
)
def test_fetch_url_content(
    url, response_text, status_code, expected_output, expected_exception
):
    with patch("requests.get") as mock_get:
        mock_get.return_value.text = response_text
        mock_get.return_value.status_code = status_code

        if expected_exception:
            with pytest.raises(expected_exception):
                fetch_url_content(url)
        else:
            assert fetch_url_content(url) == expected_output


@pytest.mark.parametrize(
    "input, expected",
    [
        ('{"name": "John", "age": 30}', {"name": "John", "age": 30}),
        ('{name": "John", "age": 30}', None),  # Invalid JSON
    ],
)
def test_parse_json(input, expected):
    if expected is None:
        with pytest.raises(json.decoder.JSONDecodeError):
            parse_json(input)
    else:
        assert parse_json(input) == expected


@pytest.mark.parametrize(
    "model_type, prompt, content, max_tokens, temperature, expected_result",
    [
        (
            "gpt-3.5-turbo-16k-0613",
            "Please summarize the following:",
            "Hello, my name is John and I am 30 years old.",
            50,
            0.0,
            "John is a 30 year old.",
        ),
        (
            "gpt-3.5-turbo-16k-0613",
            "Please generate a response:",
            "How are you?",
            20,
            0.5,
            "I'm doing well, thanks for asking!",
        ),
    ],
)
def test_chat_completion(
    model_type, prompt, content, max_tokens, temperature, expected_result
):
    with patch("openai.ChatCompletion.create") as mock_create:
        mock_create.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": expected_result,
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        result = chat_completion(model_type, prompt, content, max_tokens, temperature)
        assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text_summary, metadata, expected_result",
    [
        (
            "Hello, my name is John and I am 30 years old.",
            {"type": "generic"},
            ["'John' 'has-age' '30'"],
        ),
        (
            "We propose a new method for image classification using convolutional neural networks.",
            {
                "type": "arxiv",
                "title": "A New Image Classification Method",
                "authors": ["John Doe", "Jane Doe"],
            },
            [
                "'A New Image Classification Method' 'has-author' 'John Doe'",
                "'A New Image Classification Method' 'has-author' 'Jane Doe'",
                "'A New Image Classification Method' 'has-concept' 'image-classification'",
                "'A New Image Classification Method' 'has-concept' 'convolutional-neural-networks'",
            ],
        ),
        (
            "This is a repository for building a chatbot using PyTorch.",
            {"type": "github-repo", "repo_name": "chatbot-pytorch"},
            [
                "'chatbot-pytorch' 'implemented-in' 'Python'",
                "'chatbot-pytorch' 'has-concept' 'chatbot'",
                "'chatbot-pytorch' 'has-concept' 'PyTorch'",
            ],
        ),
    ],
)
async def test_text_to_triplets(text_summary, metadata, expected_result):
    load_dotenv()
    logger = Logger("test_text_to_triplets")
    with patch("taotie.utils.chat_completion") as mock_chat_completion:
        mock_chat_completion.return_value = json.dumps({"triplets": expected_result})
        result = await text_to_triplets(text_summary, metadata, logger)
        assert result == expected_result


@pytest.mark.parametrize(
    "triplets, expected_image_path",
    [
        (
            ["'John' 'has-age' '30'", "'Jane' 'has-age' '35'"],
            "knowledge_graph_",
        )
    ],
)
def test_construct_knowledge_graph_generates_image(triplets, expected_image_path):
    with patch("matplotlib.pyplot") as mock_plt:
        mock_plt.savefig.return_value = None
        mock_plt.clf.return_value = None
        knowledge_graph_image_path = construct_knowledge_graph(triplets, logger=None)
        assert knowledge_graph_image_path.startswith(expected_image_path)
        assert os.path.exists(knowledge_graph_image_path)
        os.remove(knowledge_graph_image_path)


@pytest.mark.parametrize(
    "url, status_code, expected",
    [
        ("https://example.com", 200, True),
        ("https://example.com", 404, False),
        ("https://example.invalid", None, False),
    ],
)
def test_check_url_exists(url, status_code, expected):
    with patch("requests.head") as mock_head:
        mock_head.return_value.status_code = status_code
        result = check_url_exists(url)
        assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repo_name, readme_response, chat_completion_response, check_url_exists_response, expected_result, readme_url",
    [
        (
            "test-repo",
            "# Hello\n![image](https://example.com/image.png)",
            '{"image_url": "https://example.com/image.png"}',
            True,
            "https://i.imgur.com/image.png",
            "https://raw.githubusercontent.com/test-repo/master/README.md",
        ),
        (
            "test-repo-invalid-url",
            "# Hello\n![image](https://example.invalid/image.png)",
            '{"image_url": "https://example.invalid/image.png"}',
            False,
            "",
            "https://raw.githubusercontent.com/test-repo-invalid-url/master/README.md",
        ),
        (
            "test-repo-no-image",
            "# Hello",
            '{"image_url": ""}',
            False,
            "",
            "https://raw.githubusercontent.com/test-repo-no-image/master/README.md",
        ),
    ],
)
async def test_extract_representative_image(
    repo_name,
    readme_response,
    chat_completion_response,
    check_url_exists_response,
    expected_result,
    readme_url,
):
    logger = Logger("test_extract_representative_image")
    with patch("requests.get") as mock_get:
        mock_get.return_value.text = readme_response
        mock_get.return_value.status_code = 200
        with patch("taotie.utils.chat_completion") as mock_chat_completion:
            mock_chat_completion.return_value = chat_completion_response
            with patch("taotie.utils.check_url_exists") as mock_check_url_exists:
                mock_check_url_exists.return_value = check_url_exists_response
                with patch(
                    "taotie.utils.save_image_to_imgur"
                ) as mock_save_image_to_imgur:
                    mock_save_image_to_imgur.return_value = expected_result
                    result = await extract_representative_image(
                        repo_name=repo_name, readme_url=readme_url, logger=logger
                    )
                    assert result == expected_result
