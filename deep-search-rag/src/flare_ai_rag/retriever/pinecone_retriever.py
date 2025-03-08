from typing import override
import structlog
from pinecone import Pinecone

from flare_ai_rag.ai import EmbeddingTaskType, GeminiEmbedding
from flare_ai_rag.retriever.base import BaseRetriever
from flare_ai_rag.retriever.config import RetrieverConfig

logger = structlog.get_logger(__name__)


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
        # Convert the query into a vector embedding using Gemini
        query_vector = self.embedding_client.embed_content(
            embedding_model=self.retriever_config.embedding_model,
            contents=query,
            task_type=EmbeddingTaskType.RETRIEVAL_QUERY,
        )

        # Search Pinecone for similar vectors, retrieving more results initially
        # to account for potential filtering of chunks from the same document
        search_limit = top_k * 5  # Retrieve more results initially (increased from 3x to 5x)
        
        # Query the Pinecone index
        results = self.index.query(
            vector=query_vector,
            top_k=search_limit,
            include_metadata=True
        )

        # Group chunks by parent document and track seen documents
        parent_documents = set()
        unique_results = []
        chunked_docs = {}
        
        # First pass - identify chunks and unique documents
        for match in results.matches:
            metadata = match.metadata
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
            matches.sort(key=lambda x: x.metadata.get("chunk_index", 0))
            
            # Take just the highest scoring chunks if there are too many
            if len(matches) > 5:  # Increased from 3 to 5 chunks
                matches = matches[:5]
                
            # Combine the chunks' text and maintain the highest score
            combined_text = "\n\n".join([match.metadata.get("text", "") for match in matches])
            highest_score = max([match.score for match in matches])
            
            # Create a combined metadata
            combined_metadata = matches[0].metadata.copy()
            combined_metadata["text"] = combined_text
            combined_metadata["filename"] = parent_doc
            combined_metadata["is_combined_chunks"] = True
            combined_metadata["num_chunks_combined"] = len(matches)
            
            # Create a synthetic match for the combined chunks
            combined_match = matches[0]
            combined_match.metadata = combined_metadata
            combined_match.score = highest_score
            
            unique_results.append(combined_match)
        
        # Sort by score and limit to requested number
        unique_results.sort(key=lambda x: x.score, reverse=True)
        unique_results = unique_results[:top_k]
        
        # Process and return results
        output = []
        for match in unique_results:
            metadata = match.metadata if match.metadata else {}
            text = metadata.get("text", "")
            
            # Create metadata dict excluding text
            metadata_dict = {
                field: value
                for field, value in metadata.items()
                if field != "text"
            }
            
            # Clean up metadata for presentation
            if "is_combined_chunks" in metadata_dict:
                metadata_dict["note"] = f"Document combined from {metadata_dict['num_chunks_combined']} parts"
                del metadata_dict["is_combined_chunks"]
                del metadata_dict["num_chunks_combined"]
            
            # Clean up any other internal metadata fields
            if "is_chunk" in metadata_dict:
                del metadata_dict["is_chunk"]
            if "chunk_index" in metadata_dict:
                del metadata_dict["chunk_index"] 
            if "total_chunks" in metadata_dict:
                del metadata_dict["total_chunks"]
            if "parent_document" in metadata_dict:
                del metadata_dict["parent_document"]
                
            output.append({"text": text, "score": match.score, "metadata": metadata_dict})
            
        logger.info(
            "Semantic search completed", 
            query=query, 
            results_found=len(output),
            requested=top_k
        )
        
        return output 