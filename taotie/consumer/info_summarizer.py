"""
"""
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import openai
from colorama import Fore

from taotie.consumer.base import Consumer
from taotie.storage.base import Storage
from taotie.utils import *


class InfoSummarizer(Consumer):
    """A consumer that summarize the message in batch."""

    def __init__(
        self,
        summarize_instruction: str,
        verbose: bool = False,
        dedup: bool = False,
        storage: Optional[Storage] = None,
        **kwargs,
    ):
        Consumer.__init__(self, verbose=verbose, dedup=dedup, storage=storage, **kwargs)
        self.buffer: List[str] = []
        self.buffer_size = 0
        self.max_buffer_size = kwargs.get("max_buffer_size", -1)
        self.summarize_instruction = summarize_instruction
        tags = kwargs.get(
            "CANDIDATE_TAGS",
            "AI,CV,deep-learning,GPT,LLM,foundation-model,HuggingFace,image-generation,"
            "inference,knowledge-extraction,language-model,machine-learning,model,"
            "model-generation,NLP,QA,chatbot,speech-recognition,text-generation,"
            "text-to-speech,training,voice-recognition",
        )
        if not self.summarize_instruction:
            self.summarize_instruction = f"""
            Please follow the instructions below to generate the json formated response:
            1. Summarize the following collected json data wrapped by triple quotes in Chinese.

            2. Plese summarize the content CONCISELY, ACCURATELY, and COMPREHENSIVELY.
            And CONCATENATE the Chinese and English summaries with \n\n IN ONE "summary" FIELD.
            For example "summary": "这是中文总结。\\n\\nThis is an English summary."

            3. Generate at most 5 tags from {tags}. If the content is irrelevant to any of the tags, instead use tag "N/A" ONLY.

            4. Please STRICTLY follow the instructions above and output the results in ONE JSON blob, \
                and STRICTLY WRAP EACH KEY OR VALUE WITH DOUBLE QUOTES.

            Some examples:
            Example 1:
            {{
                "summary": "这是一个总结。\\n\\nThis is a summary.",
                "tags": ["tag1", "tag2"],
            }}
            Example 2:
            {{
                "summary": "Segment Anything是一个新的图像分割任务、模型和数据集项目。",
                "tags": ["deep-learning", "image-generation"],
            }}
            """
        self.max_tokens = kwargs.get("max_tokens", 800)
        self.model_type = kwargs.get("model_type", "gpt-3.5-turbo")
        self.logger.debug("PrintConsumer initialized.")

    async def _process(self, messages: List[Dict[str, Any]]) -> None:
        id = messages[0].get("id", "")
        info_type = messages[0].get("type", "")
        self.buffer.extend(map(lambda m: json.dumps(m, ensure_ascii=False), messages))
        concatenated_messages = "\n".join(self.buffer)
        self.logger.info(f"Summarizer received information: {concatenated_messages}\n")
        summary_json_str = await self.gpt_summary(concatenated_messages)
        try:
            parse_json(summary_json_str)
        except Exception as e:
            # Ask LLM to fix the potentially malformed json string.
            self.logger.warning(f"Generated summary is not in JSON, fixing...")
            response = chat_completion(
                model_type=self.model_type,
                prompt="""
                You are a json fixer that can fix various types of malformed json strings.
                Please directly return the JSON as is if it is already in a valid format.
                IF not, please fix the following json string and return the fixed string in a way that is DIRECTLY PARSABLE by json.loads().
                """,
                content=f"""
                {summary_json_str}
                """,
                max_tokens=self.max_tokens,
            )
            summary_json_str = response.choices[0].message.content
        self.logger.info(
            f"""JSON summary result after fixing:
            {summary_json_str}
            """
        )
        # Extract the representative image from the repo README.md.
        representative_image_url_str = ""
        if info_type == "github-repo":
            readme_url = f"https://raw.githubusercontent.com{id}/main/README.md"
            if not check_url_exists(readme_url):
                readme_url = f"https://raw.githubusercontent.com{id}/master/README.md"
            # Extract the representative image from the repo.
            representative_image_url_str = await extract_representative_image(
                repo_name=id, readme_url=readme_url, logger=self.logger
            )
        # Generate the knowledge graph image url.
        knowledge_graph_image_url_str = await self.knowledge_graph_summary(
            concatenated_messages, messages[0]
        )
        self.logger.info(f"Knowledge graph image url: {knowledge_graph_image_url_str}")
        # Save to storage.
        if self.storage:
            # Parse the output as json.
            try:
                processed_data = parse_json(summary_json_str)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"Failed to parse the output as json. Error: {str(e)}, the json string is [[{summary_json_str}]]"
                )
                self.buffer.clear()
                return
            try:
                # TODO: This is a hack. We should have a better way to do this.
                list_of_tuples = [(raw, processed_data) for raw in messages]
                await self.storage.save(
                    list_of_tuples,
                    image_urls=[
                        representative_image_url_str,
                        knowledge_graph_image_url_str,
                    ],
                )
                self.logger.info(f"Saved to storage.")
            except Exception as e:
                self.logger.error(f"Failed to save to storage. Error: {str(e)}")
            finally:
                self.buffer.clear()

    async def gpt_summary(self, input: str) -> str:
        """A tiny example use case of using LLM to process the gathered information."""
        input = input[: self.max_buffer_size]
        prompt = f"""
        {self.summarize_instruction}
        ```
        {input}
        ```
        """
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("Please set OPENAI_API_KEY in .env.")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = chat_completion(
            model_type=self.model_type,
            prompt=prompt,
            content=input,
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        result = response.choices[0].message.content
        self.logger.output(f"Get summary: {result}\n", color=Fore.BLUE)
        return result

    async def knowledge_graph_summary(
        self, text_summary: str, metadata: Dict[str, Any]
    ) -> str:
        try:
            rdf_triplets = await text_to_triplets(text_summary, metadata, self.logger)
            self.logger.info(f"Successfully generated triplets: \n{rdf_triplets}\n")
        except Exception as e:
            self.logger.error(f"Error generating triplets: {e}")
            return ""

        try:
            knowledge_graph_image_path = await async_construct_knowledge_graph(
                rdf_triplets
            )
            self.logger.info(
                f"Successfully generated knowledge graph image: {knowledge_graph_image_path}"
            )
        except Exception as e:
            self.logger.error(
                f"Error generating knowledge graph image from triplets: {e}"
            )
            return ""

        try:
            image_url = await upload_image_to_imgur(
                knowledge_graph_image_path, self.logger
            )
            return image_url
        except Exception as e:
            self.logger.error(f"Error uploading knowledge graph image to Imgur: {e}")
            return ""
