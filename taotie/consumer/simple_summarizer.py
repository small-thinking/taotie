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


class SimpleSummarizer(Consumer):
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
            1. Summarize the following collected json data wrapped by triple quotes in BOTH Chinese AND English.

            2. Plese summarize the content CONCISELY, ACCURATELY, and COMPREHENSIVELY.
            And CONCATENATE the Chinese and English summaries with \n\n IN ONE "summary" FIELD.
            For example "summary": "这是中文总结。\\n\\nThis is an English summary."

            3. Generate at most 5 tags from {tags}. If the content is irrelevant to any of the tags, instead use tag "N/A" ONLY.

            Please STRICTLY follow the instructions above and output the results in ONE JSON blob, like:
            {{
                "summary": "这是一个总结。\\n\\nThis is a summary.",
                "tags": ["tag1", "tag2"],
            }}
            """
        self.max_tokens = kwargs.get("max_tokens", 800)
        self.model_type = kwargs.get("model_type", "gpt-3.5-turbo")
        self.logger.info("PrintConsumer initialized.")

    async def _process(self, messages: List[Dict[str, Any]]) -> None:
        self.buffer.extend(map(lambda m: json.dumps(m, ensure_ascii=False), messages))
        concatenated_messages = "\n".join(self.buffer)
        self.logger.info(f"Summarizer received information: {concatenated_messages}\n")
        result = await asyncio.create_task(self.gpt_summary(concatenated_messages))
        self.logger.info(f"Summary: '{result}'")
        # Save to storage.
        if self.storage:
            # Parse the output as json.
            try:
                json_obj = json.loads(result)
                # processed_data = {"summary": json_obj.get("summary", "N/A")}
                processed_data = json_obj
                # TODO: This is a hack. We should have a better way to do this.
                list_of_tuples = [(raw, processed_data) for raw in messages]
                await self.storage.save(list_of_tuples)
                self.logger.info(f"Saved to storage.")
            except:
                self.logger.error(f"Failed to parse the output as json.")
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
        response = openai.ChatCompletion.create(
            model=self.model_type,
            messages=[
                {
                    "role": "system",
                    "content": f"{self.summarize_instruction}",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        result = response.choices[0].message.content
        self.logger.output(f"Summary: {result}\n", color=Fore.BLUE)
        return result
