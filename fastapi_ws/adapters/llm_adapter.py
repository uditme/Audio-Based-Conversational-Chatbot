import os
import asyncio
import logging
from typing import AsyncGenerator
import google.generativeai as genai

logger = logging.getLogger(__name__)

class LLMAdapter:
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Yields string tokens/chunks
        """
        yield ""

class DummyLLMAdapter(LLMAdapter):
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        dummy_text = "This is a response from the dummy LLM adapter. I received your message: " + prompt
        tokens = dummy_text.split(" ")
        for token in tokens:
            await asyncio.sleep(0.1)
            yield token + " "

class GeminiLLMAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        try:
            response = await self.model.generate_content_async(prompt, stream=True)
            async for chunk in response:

                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            yield f" [Error calling Gemini: {e}]"

def get_llm_adapter():
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key != "replace_me":
        logger.info("Using Gemini LLM Adapter")
        return GeminiLLMAdapter(api_key)
    logger.info("Using Dummy LLM Adapter")
    return DummyLLMAdapter()
