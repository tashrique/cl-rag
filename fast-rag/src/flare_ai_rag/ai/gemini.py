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
RATE_LIMIT_ENABLED = False  # Disable rate limiting
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
        Generate a response to a prompt.

        Args:
            prompt (str): The prompt to send
            response_mime_type: Optional mime type for structuring the response
            response_schema: Optional JSON schema for structuring the response

        Returns:
            ModelResponse: The generated response
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
                    metadata={}
                )
                
            return ModelResponse(
                text=response.text,
                raw_response=response,
                metadata={"candidate_count": len(response.candidates) if response.candidates else 0}
            )
        except Exception as e:
            self.logger.error("generate_failed", error=str(e), prompt=prompt[:100])
            return ModelResponse(
                text=f"I'm having trouble processing your request: {str(e)}",
                raw_response=None,
                metadata={}
            )

    @override
    def send_message(
        self,
        msg: str,
    ) -> ModelResponse:
        """
        Send a message to the model and get a response.

        Args:
            message (str): The message to send

        Returns:
            ModelResponse: The AI's response
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
                metadata={"candidate_count": len(response.candidates) if response.candidates else 0}
            )
        except Exception as e:
            self.logger.error("send_message_failed", error=str(e))
            # Provide a failover response or re-raise the exception
            return ModelResponse(
                text=f"I'm having trouble processing your request: {str(e)}",
                raw_response=None,
                metadata={}
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
        task_type: Any = "RETRIEVAL_DOCUMENT",
        title: str = None,
    ) -> list[float]:
        """
        Generate embeddings for the given content.

        Args:
            embedding_model (str): The embedding model to use
            contents (str): Content to embed
            task_type (Any): The task type as string or enum (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)
            title (str, optional): Optional title for the content

        Returns:
            list[float]: A list of floats representing the embedding vector
        """
        try:
            # Convert the content to text to avoid serialization errors
            text_content = str(contents)

            # Determine which task type enum to use based on the input
            task_type_enum = None
            
            # If it's already an enum, use it directly
            if isinstance(task_type, EmbeddingTaskType):
                task_type_enum = task_type
            # If it has a value attribute (like an enum might), get the value
            elif hasattr(task_type, 'value'):
                task_type_value = task_type.value
                # Convert the value to the appropriate enum
                if task_type_value == "RETRIEVAL_DOCUMENT":
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_DOCUMENT
                elif task_type_value == "RETRIEVAL_QUERY":
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_QUERY
                else:
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_DOCUMENT
            # If it's a string, convert to the appropriate enum
            elif isinstance(task_type, str):
                if task_type.upper() == "RETRIEVAL_DOCUMENT":
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_DOCUMENT
                elif task_type.upper() == "RETRIEVAL_QUERY":
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_QUERY
                else:
                    task_type_enum = EmbeddingTaskType.RETRIEVAL_DOCUMENT
            # Default to document embedding for any other type
            else:
                task_type_enum = EmbeddingTaskType.RETRIEVAL_DOCUMENT
                
            # Log what we're doing
            logger.debug("Generating embedding", 
                         model=embedding_model, 
                         content_length=len(text_content), 
                         task_type=str(task_type_enum))

            # Call the API with the enum value
            try:
                embedding_response = _embed_content(
                    model=embedding_model,
                    content=text_content,
                    task_type=task_type_enum,
                    title=title,
                )
                
                # Add detailed logging about what we received
                logger.debug("Embedding response details",
                            type=type(embedding_response).__name__,
                            has_values=hasattr(embedding_response, 'values'),
                            dir=str(dir(embedding_response))[:100])
                
                # Check if we have a values attribute
                if hasattr(embedding_response, 'values'):
                    values_attr = embedding_response.values
                    logger.debug("Values attribute details",
                                type=type(values_attr).__name__,
                                is_callable=callable(values_attr))
                    
                    # If the embedding_response is a dictionary and values is callable, 
                    # it could be a dict.values method. In this case, we need to extract the actual embedding.
                    if isinstance(embedding_response, dict):
                        if "values" in embedding_response and isinstance(embedding_response["values"], list):
                            logger.info("Found embedding vector in 'values' key of dictionary")
                            embedding_values = embedding_response["values"]
                        elif "embedding" in embedding_response and isinstance(embedding_response["embedding"], list):
                            logger.info("Found embedding vector in 'embedding' key of dictionary")
                            embedding_values = embedding_response["embedding"]
                        elif len(embedding_response) == 1 and isinstance(list(embedding_response.values())[0], list):
                            # If there's only one key in the dictionary, use its value
                            first_key = list(embedding_response.keys())[0]
                            logger.info(f"Using value of single key '{first_key}' as embedding vector")
                            embedding_values = list(embedding_response.values())[0]
                        else:
                            # Dump the dictionary keys to better understand its structure
                            logger.warning(f"Dictionary embedding structure not recognized. Keys: {list(embedding_response.keys())}")
                            # Last resort: look for the first list value in the dictionary
                            for key, value in embedding_response.items():
                                if isinstance(value, list) and len(value) > 100:  # Likely to be an embedding vector
                                    logger.info(f"Using list value from key '{key}' as embedding vector")
                                    embedding_values = value
                                    break
                            else:
                                logger.error("Could not find embedding vector in dictionary")
                                return [0.0] * 768
                    # If values is callable but not a dict method, call it to get the actual values
                    elif callable(values_attr):
                        logger.info("embedding_response.values is callable, executing it")
                        try:
                            values_result = values_attr()
                            logger.debug("Called values() successfully",
                                      result_type=type(values_result).__name__)
                            
                            # If the result is dict_values, convert to a list 
                            if hasattr(values_result, '__iter__'):
                                values_list = list(values_result)
                                # If we got a list with a single item that's a list, use the inner list
                                if len(values_list) == 1 and isinstance(values_list[0], list):
                                    logger.info("Using inner list from dict_values as embedding")
                                    embedding_values = values_list[0]
                                else:
                                    embedding_values = values_list
                            else:
                                logger.error("Result of values() is not iterable")
                                return [0.0] * 768
                        except Exception as call_err:
                            logger.error(f"Error calling values(): {str(call_err)}")
                            logger.debug("Returning zeros due to error")
                            return [0.0] * 768
                    else:
                        embedding_values = values_attr
                        
                    # Sanitize the values to ensure they're all valid floats
                    if embedding_values is None:
                        logger.warning("Embedding values is None, returning zeros")
                        return [0.0] * 768
                        
                    if not hasattr(embedding_values, '__iter__'):
                        logger.warning(f"Embedding values not iterable: {type(embedding_values).__name__}, returning zeros")
                        return [0.0] * 768
                        
                    # Convert to a list of floats, replacing any invalid values with 0.0
                    clean_values = []
                    try:
                        for val in embedding_values:
                            if isinstance(val, (int, float)) and val == val and val != float('inf') and val != float('-inf'):
                                clean_values.append(float(val))
                            else:
                                clean_values.append(0.0)
                    except Exception as iter_err:
                        logger.error(f"Error iterating through embedding values: {str(iter_err)}")
                        return [0.0] * 768
                        
                    vector_length = len(clean_values)
                    logger.debug(f"Final embedding vector length: {vector_length}")
                    
                    if vector_length != 768:
                        logger.warning(f"WARNING: Expected 768-dimensional vector but got {vector_length}-dimensional vector")
                        
                        # If the vector dimension is wrong, fallback to default
                        if vector_length < 100:  # Likely not a valid embedding
                            logger.error("Embedding dimension too small, returning default 768-dimensional vector")
                            return [0.0] * 768
                    
                    logger.debug(f"Returning {len(clean_values)} embedding values")
                    return clean_values
                else:
                    logger.warning("No 'values' attribute found in embedding response")
                    return [0.0] * 768
                    
            except Exception as api_err:
                logger.error(f"API error during embedding: {str(api_err)}")
                return [0.0] * 768
                
        except Exception as e:
            logger.error(f"Embedding error with text: '{text_content[:100]}...': {str(e)}")
            return [0.0] * 768  # Default to 768-dimensional vector of zeros

def _rate_limit():
    """Apply rate limiting to avoid hitting API quotas."""
    # Disabled as per user request
    if RATE_LIMIT_ENABLED:
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        logger.debug(f"Rate limiting applied - waiting {delay:.2f} seconds")
        time.sleep(delay)
    return
