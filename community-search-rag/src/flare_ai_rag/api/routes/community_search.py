import structlog
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flare_ai_rag.retriever import PineconeRetriever
from flare_ai_rag.responder import GeminiResponder
from flare_ai_rag.attestation import Vtpm
from typing import List, Dict, Any, Optional

logger = structlog.get_logger(__name__)
router = APIRouter()

# Global instances that will be set at runtime
_retriever_instance: PineconeRetriever = None
_responder_instance: GeminiResponder = None

# Models for request and response
class CommunitySearchRequest(BaseModel):
    """Request model for Community Search RAG API."""
    query: str = Field(..., min_length=1, description="The query to search for")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    include_sources: bool = Field(True, description="Whether to include source documents")
    include_metadata: bool = Field(True, description="Whether to include metadata")
    use_fallbacks: bool = Field(True, description="Whether to use fallbacks in case of errors")

class CommunitySearchSource(BaseModel):
    """Source document model."""
    text: str
    score: float
    metadata: Dict[str, Any] = {}

class CommunitySearchResponse(BaseModel):
    """Response model for Community Search RAG API."""
    answer: str
    sources: Optional[List[CommunitySearchSource]] = None
    error: Optional[str] = None
    success: bool = True

def sanitize_for_json(obj):
    """Make sure the object is JSON serializable."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items() if not callable(v)}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # Convert other types to string
        return str(obj)

def set_components(retriever: PineconeRetriever, responder: GeminiResponder):
    """Set the retriever and responder instances."""
    global _retriever_instance, _responder_instance
    _retriever_instance = retriever
    _responder_instance = responder

def get_retriever() -> PineconeRetriever:
    """Dependency to get the retriever instance."""
    if _retriever_instance is None:
        raise HTTPException(500, "Retriever not initialized")
    return _retriever_instance

def get_responder() -> GeminiResponder:
    """Dependency to get the responder instance."""
    if _responder_instance is None:
        raise HTTPException(500, "Responder not initialized")
    return _responder_instance

@router.post("/query", response_model=CommunitySearchResponse)
async def community_search_query(
    request: CommunitySearchRequest,
    retriever: PineconeRetriever = Depends(get_retriever),
    responder: GeminiResponder = Depends(get_responder),
):
    """
    Perform a community search query.
    
    This endpoint:
    1. Takes a query string and parameters
    2. Retrieves relevant documents using the vector database
    3. Generates a response using the LLM
    4. Returns the response and source documents
    """
    try:
        # Log the query
        logger.info(
            "Processing community search query",
            query=request.query,
            top_k=request.top_k
        )
        
        # 1. Retrieve documents
        documents = []
        try:
            documents = retriever.semantic_search(
                query=request.query,
                top_k=request.top_k
            )
            logger.info("Documents retrieved", count=len(documents))
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            if not request.use_fallbacks:
                raise
                
        # 2. Prepare sources for the response
        sources = []
        if request.include_sources and documents:
            for doc in documents:
                source = CommunitySearchSource(
                    text=doc.get("text", ""),
                    score=doc.get("score", 0.0)
                )
                if request.include_metadata and "metadata" in doc:
                    # Ensure metadata is serializable
                    source.metadata = sanitize_for_json(doc["metadata"])
                sources.append(source)
        
        # 3. Generate response
        # Prepare documents for the responder
        docs_for_responder = documents[:request.top_k]
        
        # Generate the response using the LLM
        answer = responder.generate_response(
            query=request.query,
            retrieved_documents=docs_for_responder
        )
        logger.info("Response generated")
        
        # 4. Return the result
        return CommunitySearchResponse(
            answer=answer,
            sources=sources if request.include_sources else None,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return CommunitySearchResponse(
            answer="Sorry, I encountered an error while processing your query.",
            error=str(e),
            success=False
        ) 