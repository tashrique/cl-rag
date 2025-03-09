from typing import override, Dict, Any, List
import structlog
from pinecone import Pinecone

from flare_ai_rag.ai import EmbeddingTaskType, GeminiEmbedding
from flare_ai_rag.retriever.base import BaseRetriever
from flare_ai_rag.retriever.config import RetrieverConfig

logger = structlog.get_logger(__name__)


# Helper function to ensure returned data is serializable
def _sanitize_data(obj: Any) -> Any:
    """Sanitize data to ensure it's JSON serializable."""
    # Handle None case
    if obj is None:
        return None
        
    # Handle primitive types that are already serializable
    if isinstance(obj, (str, int, float, bool)):
        # Check for NaN or infinity in floats
        if isinstance(obj, float) and (obj != obj or obj == float('inf') or obj == float('-inf')):
            return 0.0
        return obj
        
    # Handle dictionaries
    if isinstance(obj, dict):
        return {k: _sanitize_data(v) for k, v in obj.items() if not callable(v)}
        
    # Handle lists, tuples, and other iterables
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize_data(item) for item in obj]
        
    # Handle callables (functions, methods)
    if callable(obj):
        # Convert callable objects to their string representation
        return f"<function: {obj.__name__}>" if hasattr(obj, "__name__") else str(obj)
        
    # Handle objects with __dict__ (most custom classes)
    if hasattr(obj, '__dict__'):
        # For custom objects, convert to dict and sanitize it
        sanitized_dict = {k: _sanitize_data(v) for k, v in obj.__dict__.items() if not callable(v)}
        return sanitized_dict
        
    # Handle objects with __slots__
    if hasattr(obj, '__slots__'):
        # Handle objects with __slots__
        sanitized_dict = {}
        for slot in obj.__slots__:
            if hasattr(obj, slot):
                sanitized_dict[slot] = _sanitize_data(getattr(obj, slot))
        return sanitized_dict
        
    # Last resort: convert to string
    try:
        return str(obj)
    except Exception:
        return "<unserializable object>"


class PineconeRetriever(BaseRetriever):
    def __init__(
        self,
        client: Pinecone,
        retriever_config: RetrieverConfig,
        embedding_client: GeminiEmbedding,
    ) -> None:
        """Initialize the PineconeRetriever."""
        self.client = client
        self.retriever_config = retriever_config
        self.embedding_client = embedding_client
        self.index = client.Index(retriever_config.collection_name)

    @override
    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Perform semantic search by converting the query into a vector
        and searching in Pinecone.

        :param query: The input query.
        :param top_k: Number of top results to return.
        :return: A list of dictionaries, each representing a retrieved document.
        """
        try:
            logger.info(f"Starting semantic search for query: '{query}', top_k: {top_k}")
            
            # Convert the query into a vector embedding using Gemini
            logger.debug("Generating query embedding")
            query_vector = self.embedding_client.embed_content(
                embedding_model=self.retriever_config.embedding_model,
                contents=query,
                task_type="RETRIEVAL_QUERY",  # Pass task_type as a string
            )
            
            # Log the vector details
            vector_length = len(query_vector) if query_vector else 0
            logger.debug(f"Query vector generated, length: {vector_length}")
            if vector_length > 0:
                # Log a sample of the vector (first 5 values)
                sample = query_vector[:5]
                logger.debug(f"Vector sample (first 5 values): {sample}")

            # Search Pinecone for similar vectors, retrieving more results initially
            # to account for potential filtering of chunks from the same document
            search_limit = top_k * 5  # Retrieve more results initially
            logger.debug(f"Search limit set to: {search_limit}")
            
            # Ensure the query vector is a pure list of floats
            # This prevents serialization issues
            if not isinstance(query_vector, list):
                logger.warning(f"Converting query vector from {type(query_vector).__name__} to list type")
                query_vector = list(query_vector)
                
            # Validate no NaN or infinity values
            invalid_count = 0
            for i, val in enumerate(query_vector):
                if not isinstance(val, (int, float)) or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))):
                    logger.warning(f"Invalid vector value at index {i}: {val}, replacing with 0.0")
                    query_vector[i] = 0.0
                    invalid_count += 1
            
            if invalid_count > 0:
                logger.warning(f"Fixed {invalid_count} invalid values in query vector")
            
            # Query the Pinecone index
            logger.debug(f"Querying Pinecone index: {self.retriever_config.collection_name}")
            try:
                results = self.index.query(
                    vector=query_vector,
                    top_k=search_limit,
                    include_metadata=True
                )
                
                # Log the raw results
                match_count = len(results.matches) if hasattr(results, 'matches') else 0
                logger.debug(f"Pinecone returned {match_count} raw matches")
                
            except Exception as pinecone_err:
                logger.error(f"Pinecone query error: {str(pinecone_err)}")
                return []

            # Group chunks by parent document and track seen documents
            parent_documents = set()
            unique_results = []
            chunked_docs = {}
            
            # First pass - identify chunks and unique documents
            for match in results.matches:
                metadata = match.metadata if hasattr(match, 'metadata') else {}
                if not metadata:
                    continue
                    
                is_chunk = metadata.get("is_chunk", False)
                
                if is_chunk:
                    parent_doc = metadata.get("parent_document", "")
                    if parent_doc not in chunked_docs:
                        chunked_docs[parent_doc] = []
                    chunked_docs[parent_doc].append(match)
                else:
                    # Regular document
                    doc_id = metadata.get("filename", "")
                    if doc_id not in parent_documents:
                        parent_documents.add(doc_id)
                        unique_results.append(match)
                        
                        # Don't add a regular document if we already have chunks from it
                        if doc_id in chunked_docs:
                            del chunked_docs[doc_id]
            
            # Process chunks - combine chunks from the same document
            for parent_doc, matches in chunked_docs.items():
                if parent_doc in parent_documents:
                    # Skip if we already have the full document
                    continue
                    
                parent_documents.add(parent_doc)
                
                # Sort chunks by their index
                matches.sort(key=lambda x: x.metadata.get("chunk_index", 0) if hasattr(x, 'metadata') else 0)
                
                # Take just the highest scoring chunks if there are too many
                if len(matches) > 5:  # Increased from 3 to 5 chunks
                    matches = matches[:5]
                    
                # Combine the chunks' text and maintain the highest score
                combined_text = "\n\n".join([match.metadata.get("text", "") for match in matches if hasattr(match, 'metadata')])
                highest_score = max([match.score for match in matches if hasattr(match, 'score')])
                
                # Create a combined metadata dictionary directly
                combined_metadata = {}
                if matches and hasattr(matches[0], 'metadata') and matches[0].metadata:
                    combined_metadata = dict(matches[0].metadata)
                
                combined_metadata["text"] = combined_text
                combined_metadata["filename"] = parent_doc
                combined_metadata["is_combined_chunks"] = True
                combined_metadata["num_chunks_combined"] = len(matches)
                
                # Create a simple dictionary instead of modifying matches[0]
                combined_match = {
                    "metadata": combined_metadata,
                    "score": highest_score,
                    "id": f"combined_{parent_doc}"
                }
                
                unique_results.append(combined_match)
            
            # Sort by score and limit to requested number
            unique_results.sort(key=lambda x: getattr(x, 'score', 0) if hasattr(x, 'score') else x.get('score', 0), reverse=True)
            unique_results = unique_results[:top_k]
            
            # Process and return results
            output = []
            for match in unique_results:
                # Handle both dictionary and object types
                if isinstance(match, dict):
                    metadata = match.get("metadata", {})
                    text = metadata.get("text", "")
                    score = match.get("score", 0.0)
                else:
                    metadata = getattr(match, "metadata", {}) if hasattr(match, "metadata") else {}
                    text = metadata.get("text", "") if metadata else ""
                    score = getattr(match, "score", 0.0) if hasattr(match, "score") else 0.0
                
                # Create metadata dict excluding text
                metadata_dict = {}
                if metadata:
                    metadata_dict = {
                        field: value
                        for field, value in metadata.items()
                        if field != "text" and not callable(value)
                    }
                
                # Clean up metadata for presentation
                if "is_combined_chunks" in metadata_dict:
                    metadata_dict["note"] = f"Document combined from {metadata_dict.get('num_chunks_combined', 0)} parts"
                    metadata_dict.pop("is_combined_chunks", None)
                    metadata_dict.pop("num_chunks_combined", None)
                
                # Clean up any other internal metadata fields
                metadata_dict.pop("is_chunk", None)
                metadata_dict.pop("chunk_index", None)
                metadata_dict.pop("total_chunks", None)
                metadata_dict.pop("parent_document", None)
                    
                output.append({"text": text, "score": score, "metadata": metadata_dict})
                
            logger.info(
                "Semantic search completed", 
                query=query, 
                results_found=len(output),
                requested=top_k
            )
            
            # Ensure output is fully serializable
            return _sanitize_data(output)
            
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            # Return empty results on error
            return [] 