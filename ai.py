"""AI-related utilities for Telegram message processing."""

import os
from typing import Optional

from config import get_logger
from prompts import SYSTEM_PROMPT
from dotenv import load_dotenv


logger = get_logger(__name__)
load_dotenv()
try:
    from langchain_mistralai import ChatMistralAI
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    LANGCHAIN_AVAILABLE = False
    ChatMistralAI = None  # type: ignore[assignment]
    ChatPromptTemplate = None  # type: ignore[assignment]
    logger.warning("LangChain not installed. AI processing will be disabled.")


class MistralAIProcessor:
    """Process messages using the Mistral AI API via LangChain."""

    def __init__(self, api_key: Optional[str] = None, custom_prompt: Optional[str] = None):
        if not LANGCHAIN_AVAILABLE:
            self.enabled = False
            return

        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            logger.warning("Mistral API key not found. AI processing will be disabled.")
            self.enabled = False
            return

        self.enabled = True

        try:
            self.llm = ChatMistralAI(
                api_key=self.api_key,
                model="mistral-tiny",
                temperature=0.7,
                max_tokens=500,
            )

            default_prompt = """You are an intelligent message analyzer. Analyze the following Telegram message and provide insights:

Message Details:
Channel: {channel_name}
Sender: {sender_name}
Date: {message_date}
Text: {message_text}

Please provide:
1. A brief summary
2. Key topics or themes
3. Sentiment analysis
4. Any important entities mentioned
5. Overall assessment

Keep your response concise and informative."""

            self.prompt_template = ChatPromptTemplate.from_template(
                custom_prompt or default_prompt
            )

        except Exception as exc:  # pragma: no cover - network failures etc.
            logger.error("Failed to initialize Mistral AI model: %s", exc)
            self.enabled = False

    async def process_message(self, message_data: dict) -> Optional[str]:
        """Process a message using Mistral AI via LangChain."""
        if not self.enabled:
            return None

        try:
            chain = self.prompt_template | self.llm
            response = await chain.ainvoke(message_data)
            return response.content
        except Exception as exc:  # pragma: no cover - runtime errors from API
            logger.error("Error processing message with Mistral AI: %s", exc)
            return None

    async def is_message_relevant(self, message_text: str, user_query: str) -> bool:
        """Check if a message is relevant to the user's query using LLM."""
        if not self.enabled:
            return True

        try:
            relevance_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
            chain = relevance_prompt | self.llm
            response = await chain.ainvoke(
                {
                    "user_query": user_query,
                    "message_text": message_text,
                }
            )
            response_text = (
                str(response.content) if hasattr(response, "content") else str(response)
            ).strip().upper()
            logger.info("LLM relevance response: %s", response_text)
            if response_text.startswith("NOT RELEVANT"):
                return False
            if response_text.startswith("RELEVANT"):
                return True
            logger.warning("Unexpected LLM response format: %s", response_text)
            return True
        except Exception as exc:  # pragma: no cover - runtime errors from API
            logger.error("Error checking message relevance: %s", exc)
            return True