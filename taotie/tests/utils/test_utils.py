"""Test the utils.
Run this test with command: pytest taotie/tests/utils/test_utils.py
"""
from unittest.mock import MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion_message import FunctionCall
from openai.types.edit import Choice

from taotie.utils.utils import *


@pytest.mark.parametrize(
    "input, expected",
    [(1681684094, "2023-04-16 14:28:14")],
)
def test_get_datetime(input, expected):
    assert get_datetime(input) == expected


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
            "gpt-3.5-turbo-1106",
            "Please summarize the following:",
            "Hello, my name is John and I am 30 years old.",
            50,
            0.0,
            "John is a 30 year old.",
        ),
        (
            "gpt-3.5-turbo-1106",
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
    with patch.dict(os.environ, {"OPENAI_API_KEY": "your_mocked_api_key"}):
        # Mock the OpenAI constructor
        with patch("openai.OpenAI") as MockOpenAI:
            mock_openai_instance = MockOpenAI.return_value

            # Set up the mock for chat.completions.create method
            mock_openai_instance.chat.completions.create.return_value = ChatCompletion(
                id="chatcmpl-123",
                created=1677652288,
                model="gpt-3.5-turbo-1106",
                object="chat.completion",
                choices=[
                    Choice(
                        message=ChatCompletionMessage(
                            role="assistant", content=expected_result
                        ),
                        finish_reason="stop",
                        index=0,
                        text="aaa",
                    )
                ],
            )

            # Call the function under test
            result = chat_completion(
                model_type,
                prompt,
                content,
                max_tokens,
                temperature,
                client=mock_openai_instance,
            )

            # Assertions
            assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text_summary, metadata, model_type, max_tokens, expected_output",
    [
        (
            "This is a test summary",
            {
                "createdDate": "2021-09-15",
                "lastUpdated": "2021-09-15",
                "description": "Test",
            },
            "gpt-3.5-turbo-1106",
            6000,
            {
                "metadata": {
                    "createdDate": "2021-09-15",
                    "lastUpdated": "2021-09-15",
                    "description": "Test",
                },
                "nodes": [
                    {
                        "id": "1",
                        "label": "Test Summary",
                        "type": "Summary",
                        "color": "#FFD700",
                    }
                ],
                "edges": [],
            },
        ),
    ],
)
async def test_text_to_triplets(
    text_summary, metadata, model_type, max_tokens, expected_output
):
    logger = Logger("test_logger")
    with patch("taotie.utils.utils.chat_completion") as mock_chat_completion:
        # Mock response as an object, not JSON
        mock_chat_completion.return_value = ChatCompletion(
            id="chatcmpl-123",
            created=1677652288,
            model="gpt-3.5-turbo-1106",
            object="chat.completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    text="",
                    message=ChatCompletionMessage(
                        role="assistant",
                        function_call=FunctionCall(
                            name="", arguments=json.dumps(expected_output)
                        ),
                    ),
                )
            ],
        )
        result = await text_to_triplets(
            text_summary, metadata, logger, model_type, max_tokens
        )
        assert isinstance(result, Dict)


@pytest.mark.parametrize(
    "triplets, expected_output",
    [
        (
            {
                "nodes": [
                    {"id": "1", "label": "Node1", "color": "red"},
                    {"id": "2", "label": "Node2", "color": "blue"},
                ],
                "edges": [
                    {
                        "from": "1",
                        "to": "2",
                        "relationship": "connects",
                        "color": "green",
                    }
                ],
            },
            "knowledge_graph_",
        ),
        # Add more test cases here
    ],
)
def test_construct_knowledge_graph(triplets, expected_output):
    logger = Logger("test_logger")
    result = construct_knowledge_graph(triplets, logger)
    assert (
        expected_output in result
    )  # Modify this line based on what you actually expect
    assert os.path.exists(result)  # Check if the file actually exists
    os.remove(result)  # Clean up the generated image file


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
        with patch("taotie.utils.utils.chat_completion") as mock_chat_completion:
            mock_chat_completion.return_value = chat_completion_response
            with patch("taotie.utils.utils.check_url_exists") as mock_check_url_exists:
                mock_check_url_exists.return_value = check_url_exists_response
                with patch(
                    "taotie.utils.utils.save_image_to_imgur"
                ) as mock_save_image_to_imgur:
                    mock_save_image_to_imgur.return_value = expected_result
                    result = await extract_representative_image(
                        repo_name=repo_name, readme_url=readme_url, logger=logger
                    )
                    assert result == expected_result
