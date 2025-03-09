from typing import Any, override

from flare_ai_rag.ai import GeminiProvider, OpenRouterClient
from flare_ai_rag.responder import BaseResponder, ResponderConfig
from flare_ai_rag.utils import parse_chat_response


class GeminiResponder(BaseResponder):
    def __init__(
        self, client: GeminiProvider, responder_config: ResponderConfig
    ) -> None:
        """
        Initialize the responder with a GeminiProvider.

        :param client: An instance of OpenRouterClient.
        :param model: The model identifier to be used by the API.
        """
        self.client = client
        self.responder_config = responder_config

    @override
    def generate_response(self, query: str, retrieved_documents: list[dict]) -> str:
        """
        Generate a final answer using the query and the retrieved context.

        :param query: The input query.
        :param retrieved_documents: A list of dictionaries containing retrieved docs.
        :return: The generated answer as a string.
        """
        context = "List of retrieved documents:\n"

        # Build context from the retrieved documents with more structured information
        for idx, doc in enumerate(retrieved_documents, start=1):
            metadata = doc.get("metadata", {})
            filename = metadata.get("filename", f"Document{idx}")
            source_url = metadata.get("source", "")  # Get source URL if available
            last_updated = metadata.get("last_updated", "")
            
            # Structure the document information more clearly
            context += f"Document ID: {filename}\n"
            if source_url:
                context += f"Source URL: {source_url}\n"
            if last_updated:
                context += f"Last Updated: {last_updated}\n"
            context += f"Content:\n{doc.get('text', '')}\n\n"

        # Compose the prompt
        prompt = context + f"User query: {query}\n" + self.responder_config.query_prompt

        # Use the generate method of GeminiProvider to obtain a response.
        response = self.client.generate(
            prompt,
            response_mime_type=None,
            response_schema=None,
        )
        
        # Post-process the response to ensure HTML links are properly formatted
        response_text = self._post_process_links(response.text, retrieved_documents)
        
        return response_text
    
    def _post_process_links(self, text: str, documents: list[dict]) -> str:
        """
        Post-process the response text to ensure HTML links are properly formatted.
        Converts "source:" links to actual university website URLs or Common Data Set pages.
        
        :param text: The response text from the LLM
        :param documents: The retrieved documents used for the response
        :return: The processed text with properly formatted HTML links
        """
        import re
        
        # Create a mapping of document filenames to their metadata for quick lookup
        doc_map = {doc.get("metadata", {}).get("filename", f"Doc{i}"): doc 
                   for i, doc in enumerate(documents, 1)}
        
        # Pattern to find HTML links with source: format
        pattern = r'<a href="source:([^"]+)">([^<]+)</a>'
        
        def replace_link(match: re.Match) -> str:
            university_name = match.group(1)
            link_text = match.group(2)
            
            # Check if we have metadata with a URL for this university
            if university_name in doc_map:
                metadata = doc_map[university_name].get("metadata", {})
                # Check if there's a source URL in the metadata
                url = metadata.get("source", "")
                
                if url and url.startswith(("http://", "https://")):
                    # If we have a valid URL, use it
                    return f'<a href="{url}" target="_blank">{link_text}</a>'
            
            # If no valid URL found, create a Common Data Set URL
            # Clean the university name for use in a URL
            clean_name = university_name.lower().replace(" ", "-").replace(",", "")
            # Generate Common Data Set URL
            cds_url = f"https://{clean_name}.edu/about/common-data-set"
            
            return f'<a href="{cds_url}" target="_blank">{link_text}</a>'
        
        # Replace all source: links with proper URLs
        processed_text = re.sub(pattern, replace_link, text)
        
        return processed_text


class OpenRouterResponder(BaseResponder):
    def __init__(
        self, client: OpenRouterClient, responder_config: ResponderConfig
    ) -> None:
        """
        Initialize the responder with an OpenRouter client and the model to use.

        :param client: An instance of OpenRouterClient.
        :param model: The model identifier to be used by the API.
        """
        self.client = client
        self.responder_config = responder_config

    @override
    def generate_response(self, query: str, retrieved_documents: list[dict]) -> str:
        """
        Generate a final answer using the query and the retrieved context,
        and include citations.

        :param query: The input query.
        :param retrieved_documents: A list of dictionaries containing retrieved docs.
        :return: The generated answer as a string.
        """
        context = "List of retrieved documents:\n"

        # Build context from the retrieved documents with more structured information
        for idx, doc in enumerate(retrieved_documents, start=1):
            metadata = doc.get("metadata", {})
            filename = metadata.get("filename", f"Document{idx}")
            source_url = metadata.get("source", "")  # Get source URL if available
            last_updated = metadata.get("last_updated", "")
            
            # Structure the document information more clearly
            context += f"Document ID: {filename}\n"
            if source_url:
                context += f"Source URL: {source_url}\n"
            if last_updated:
                context += f"Last Updated: {last_updated}\n"
            context += f"Content:\n{doc.get('text', '')}\n\n"

        # Compose the prompt
        prompt = context + f"User query: {query}\n" + self.responder_config.query_prompt
        # Prepare the payload for the completion endpoint.
        payload: dict[str, Any] = {
            "model": self.responder_config.model.model_id,
            "messages": [
                {"role": "system", "content": self.responder_config.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

        if self.responder_config.model.max_tokens is not None:
            payload["max_tokens"] = self.responder_config.model.max_tokens
        if self.responder_config.model.temperature is not None:
            payload["temperature"] = self.responder_config.model.temperature

        # Send the prompt to the OpenRouter API.
        response = self.client.send_chat_completion(payload)
        response_text = parse_chat_response(response)
        
        # Post-process the response to ensure HTML links are properly formatted
        response_text = self._post_process_links(response_text, retrieved_documents)
        
        return response_text
    
    def _post_process_links(self, text: str, documents: list[dict]) -> str:
        """
        Post-process the response text to ensure HTML links are properly formatted.
        Converts "source:" links to actual university website URLs or Common Data Set pages.
        
        :param text: The response text from the LLM
        :param documents: The retrieved documents used for the response
        :return: The processed text with properly formatted HTML links
        """
        import re
        
        # Create a mapping of document filenames to their metadata for quick lookup
        doc_map = {doc.get("metadata", {}).get("filename", f"Doc{i}"): doc 
                   for i, doc in enumerate(documents, 1)}
        
        # Pattern to find HTML links with source: format
        pattern = r'<a href="source:([^"]+)">([^<]+)</a>'
        
        def replace_link(match: re.Match) -> str:
            university_name = match.group(1)
            link_text = match.group(2)
            
            # Check if we have metadata with a URL for this university
            if university_name in doc_map:
                metadata = doc_map[university_name].get("metadata", {})
                # Check if there's a source URL in the metadata
                url = metadata.get("source", "")
                
                if url and url.startswith(("http://", "https://")):
                    # If we have a valid URL, use it
                    return f'<a href="{url}" target="_blank">{link_text}</a>'
            
            # If no valid URL found, create a Common Data Set URL
            # Clean the university name for use in a URL
            clean_name = university_name.lower().replace(" ", "-").replace(",", "")
            # Generate Common Data Set URL
            cds_url = f"https://{clean_name}.edu/about/common-data-set"
            
            return f'<a href="{cds_url}" target="_blank">{link_text}</a>'
        
        # Replace all source: links with proper URLs
        processed_text = re.sub(pattern, replace_link, text)
        
        return processed_text
