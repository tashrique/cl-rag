"""
Gemini AI Provider Module

This module implements the Gemini AI provider for the AI Agent API, integrating
with Google's Generative AI service. It handles chat sessions, content generation,
and message management while maintaining a consistent AI personality.
"""

from typing import Any, override
import time
import random

import structlog
from google.generativeai.client import configure
from google.generativeai.embedding import (
    EmbeddingTaskType,
)
from google.generativeai.embedding import (
    embed_content as _embed_content,
)
from google.generativeai.generative_models import ChatSession, GenerativeModel
from google.generativeai.types import GenerationConfig

from flare_ai_rag.ai.base import BaseAIProvider, ModelResponse

logger = structlog.get_logger(__name__)

# Add rate limiting parameters
RATE_LIMIT_ENABLED = True
MIN_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 3.0

SYSTEM_INSTRUCTION = """
You are Deep-Search RAG, a college application assistant that specializes in comprehensive, 
detailed responses for complex academic questions.

When helping users:
- Provide accurate information about universities, admissions, and scholarships
- Include specific details like statistics, requirements, and deadlines
- Reference the information sources in your responses
- Format your answers clearly and logically

Your goal is to help students navigate the college application process with 
reliable and detailed information based on the latest available data.
"""


class GeminiProvider(BaseAIProvider):
    """
    Provider class for Google's Gemini AI service.

    This class implements the BaseAIProvider interface to provide AI capabilities
    through Google's Gemini models. It manages chat sessions, generates content,
    and maintains conversation history.

    Attributes:
        chat (generativeai.ChatSession | None): Active chat session
        model (generativeai.GenerativeModel): Configured Gemini model instance
        chat_history: History of chat interactions
        logger (BoundLogger): Structured logger for the provider
    """

    def __init__(self, api_key: str, model: str, **kwargs: str) -> None:
        """
        Initialize the Gemini provider with API credentials and model configuration.

        Args:
            api_key (str): Google API key for authentication
            model (str): Gemini model identifier to use
            **kwargs (str): Additional configuration parameters including:
                - system_instruction: Custom system prompt for the AI personality
        """
        configure(api_key=api_key)
        self.chat: ChatSession | None = None
        self.model = GenerativeModel(
            model_name=model,
            system_instruction=kwargs.get("system_instruction", SYSTEM_INSTRUCTION),
        )
        self.chat_history = []
        self.logger = logger.bind(service="gemini")

    @override
    def reset(self) -> None:
        """
        Reset the provider state.

        Clears chat history and terminates active chat session.
        """
        self.chat_history = []
        self.chat = None
        self.logger.debug(
            "reset_gemini", chat=self.chat, chat_history=self.chat_history
        )

    @override
    def reset_model(self, model: str, **kwargs: str) -> None:
        """
        Completely reinitialize the generative model with new parameters,
        and reset the chat session and history.

        Args:
            model (str): New model identifier.
            **kwargs: Additional configuration parameters, e.g.:
                system_instruction: new system prompt.
        """
        new_system_instruction = kwargs.get("system_instruction", SYSTEM_INSTRUCTION)
        # Reinitialize the generative model.
        self.model = GenerativeModel(
            model_name=model,
            system_instruction=new_system_instruction,
        )
        # Reset chat session and history with the new system instruction.
        self.chat = None
        self.chat_history = [{"role": "system", "content": new_system_instruction}]
        self.logger.debug(
            "reset_model", model=model, system_instruction=new_system_instruction
        )

    @override
    def generate(
        self,
        prompt: str,
        response_mime_type: str | None = None,
        response_schema: Any | None = None,
    ) -> ModelResponse:
        """
        Generate content using the Gemini model.

        Args:
            prompt (str): Input prompt for content generation
            response_mime_type (str | None): Expected MIME type for the response
            response_schema (Any | None): Schema defining the response structure

        Returns:
            ModelResponse: Generated content with metadata including:
                - text: Generated text content
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input prompt
        """
        _rate_limit()  # Apply rate limiting
        generation_config = {}
        
        if response_mime_type:
            generation_config["response_mime_types"] = [response_mime_type]
        
        if response_schema:
            generation_config["schema"] = response_schema
            
        config = GenerationConfig(**generation_config) if generation_config else None
        
        try:
            response = self.model.generate_content(prompt, generation_config=config)
            
            if response.candidates and not response.candidates[0].content.parts:
                self.logger.warning("empty_response_from_gemini", prompt=prompt[:100])
                return ModelResponse(
                    text="I don't have a response for that.",
                    raw_response=response,
                    model=None
                )
                
            return ModelResponse(
                text=response.text,
                raw_response=response,
                model=response.candidates[0].content.parts  # Type?
            )
        except Exception as e:
            self.logger.error("generate_failed", error=str(e), prompt=prompt[:100])
            return ModelResponse(
                text=f"I'm having trouble processing your request: {str(e)}",
                raw_response=None,
                model=None
            )

    @override
    def send_message(
        self,
        msg: str,
    ) -> ModelResponse:
        """
        Send a message in a chat session and get the response.

        Initializes a new chat session if none exists, using the current chat history.

        Args:
            msg (str): Message to send to the chat session

        Returns:
            ModelResponse: Response from the chat session including:
                - text: Generated response text
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input message
        """
        _rate_limit()  # Apply rate limiting
        try:
            if self.chat is None:
                self.chat = self.model.start_chat(history=self.chat_history)

            response = self.chat.send_message(msg)
            self.logger.debug("response", response=response)
            
            return ModelResponse(
                text=response.text,
                raw_response=response,
                model=response.candidates[0].content.parts  # Type?
            )
        except Exception as e:
            self.logger.error("send_message_failed", error=str(e))
            # Provide a failover response or re-raise the exception
            return ModelResponse(
                text=f"I'm having trouble processing your request: {str(e)}",
                raw_response=None,
                model=None
            )


class GeminiEmbedding:
    """
    Provides embedding functionality using Google's Gemini models.
    """

    def __init__(self, api_key: str) -> None:
        """
        Initialize the embedding client with API key.

        Args:
            api_key (str): API key for Google Generative AI
        """
        configure(api_key=api_key)

    def embed_content(
        self,
        embedding_model: str,
        contents: str,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        title: str = None,
    ) -> list[float]:
        """
        Generate embeddings for the given content.

        Args:
            embedding_model (str): The embedding model to use
            contents (str): Content to embed
            task_type (EmbeddingTaskType): The task type for which embeddings are generated
            title (str, optional): Optional title for the content

        Returns:
            list[float]: A list of floats representing the embedding vector
        """
        # Apply rate limiting
        _rate_limit()
        try:
            # Convert the content to text to avoid serialization errors
            text_content = str(contents)

            embedding = _embed_content(
                model=embedding_model,
                content=text_content,
                task_type=task_type,
                title=title,
            )
            return embedding.values
        except Exception as e:
            msg = f"Embedding error with text: '{text_content[:100]}...': {str(e)}"
            logger.error(msg)
            raise ValueError(msg) from e

def _rate_limit():
    """Apply rate limiting to avoid hitting API quotas."""
    if RATE_LIMIT_ENABLED:
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        logger.debug(f"Rate limiting applied - waiting {delay:.2f} seconds")
        time.sleep(delay)
