from typing import override
import structlog
from qdrant_client import QdrantClient

from flare_ai_rag.ai import EmbeddingTaskType, GeminiEmbedding
from flare_ai_rag.retriever.base import BaseRetriever
from flare_ai_rag.retriever.config import RetrieverConfig

logger = structlog.get_logger(__name__)


class QdrantRetriever(BaseRetriever):
    def __init__(
        self,
        client: QdrantClient,
        retriever_config: RetrieverConfig,
        embedding_client: GeminiEmbedding,
    ) -> None:
        """Initialize the QdrantRetriever."""
        self.client = client
        self.retriever_config = retriever_config
        self.embedding_client = embedding_client

    @override
    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Perform semantic search by converting the query into a vector
        and searching in Qdrant.

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

        # Search Qdrant for similar vectors, retrieving more results initially
        # to account for potential filtering of chunks from the same document
        search_limit = top_k * 5  # Retrieve more results initially (increased from 3x to 5x)
        results = self.client.search(
            collection_name=self.retriever_config.collection_name,
            query_vector=query_vector,
            limit=search_limit,
        )

        # Group chunks by parent document and track seen documents
        parent_documents = set()
        unique_results = []
        chunked_docs = {}
        
        # First pass - identify chunks and unique documents
        for hit in results:
            if not hit.payload:
                continue
                
            is_chunk = hit.payload.get("is_chunk", False)
            
            if is_chunk:
                parent_doc = hit.payload.get("parent_document", "")
                if parent_doc not in chunked_docs:
                    chunked_docs[parent_doc] = []
                chunked_docs[parent_doc].append(hit)
            else:
                # Regular document
                doc_id = hit.payload.get("filename", "")
                if doc_id not in parent_documents:
                    parent_documents.add(doc_id)
                    unique_results.append(hit)
                    
                    # Don't add a regular document if we already have chunks from it
                    if doc_id in chunked_docs:
                        del chunked_docs[doc_id]
        
        # Process chunks - combine chunks from the same document
        for parent_doc, hits in chunked_docs.items():
            if parent_doc in parent_documents:
                # Skip if we already have the full document
                continue
                
            parent_documents.add(parent_doc)
            
            # Sort chunks by their index
            hits.sort(key=lambda x: x.payload.get("chunk_index", 0))
            
            # Take just the highest scoring chunks if there are too many
            if len(hits) > 5:  # Increased from 3 to 5 chunks
                hits = hits[:5]
                
            # Combine the chunks' text and maintain the highest score
            combined_text = "\n\n".join([hit.payload.get("text", "") for hit in hits])
            highest_score = max([hit.score for hit in hits])
            
            # Create a combined payload
            combined_payload = hits[0].payload.copy()
            combined_payload["text"] = combined_text
            combined_payload["filename"] = parent_doc
            combined_payload["is_combined_chunks"] = True
            combined_payload["num_chunks_combined"] = len(hits)
            
            # Create a synthetic hit for the combined chunks
            combined_hit = hits[0]
            combined_hit.payload = combined_payload
            combined_hit.score = highest_score
            
            unique_results.append(combined_hit)
        
        # Sort by score and limit to requested number
        unique_results.sort(key=lambda x: x.score, reverse=True)
        unique_results = unique_results[:top_k]
        
        # Process and return results
        output = []
        for hit in unique_results:
            if hit.payload:
                text = hit.payload.get("text", "")
                metadata = {
                    field: value
                    for field, value in hit.payload.items()
                    if field != "text"
                }
                
                # Clean up metadata for presentation
                if "is_combined_chunks" in metadata:
                    metadata["note"] = f"Document combined from {metadata['num_chunks_combined']} parts"
                    del metadata["is_combined_chunks"]
                    del metadata["num_chunks_combined"]
                
                # Clean up any other internal metadata fields
                if "is_chunk" in metadata:
                    del metadata["is_chunk"]
                if "chunk_index" in metadata:
                    del metadata["chunk_index"] 
                if "total_chunks" in metadata:
                    del metadata["total_chunks"]
                if "parent_document" in metadata:
                    del metadata["parent_document"]
            else:
                text = ""
                metadata = {}
                
            output.append({"text": text, "score": hit.score, "metadata": metadata})
            
        logger.info(
            "Semantic search completed", 
            query=query, 
            results_found=len(output),
            requested=top_k
        )
        
        return output
    
"""
Items to extract
- University Name
- Location
- Description
- Website
- Acceptance Rate
- Average GPA
- Average SAT Score
- Average ACT Score
- Average TOEFL Score
- Average IELTS Score
- Average GRE Score
- Average GMAT Score
- Average LSAT Score
- Average MCAT Score
- Average GRE Score
- Graduation Rate
- Student Population
- Undergraduate Population
- Graduate Population
- International Student Population
- Domestic Student Population
- Student Body Diversity
- Student Body Gender Ratio
- Student Body Ethnic Diversity
- Student Body International Diversity
- Student Body US Domestic Diversity
- Student Body Rural Diversity
- Student Body Urban Diversity
- Student Body Suburban Diversity

"""
