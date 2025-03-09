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
class FastSearchRequest(BaseModel):
    """Request model for Fast Search RAG API."""
    query: str = Field(..., min_length=1, description="The query to search for")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    include_sources: bool = Field(True, description="Whether to include source documents")
    include_metadata: bool = Field(True, description="Whether to include metadata")
    use_fallbacks: bool = Field(True, description="Whether to use fallbacks in case of errors")

class FastSearchSource(BaseModel):
    """Source document model."""
    text: str
    score: float
    metadata: Dict[str, Any] = {}

class FastSearchResponse(BaseModel):
    """Response model for Fast Search RAG API."""
    answer: str
    sources: Optional[List[FastSearchSource]] = None
    error: Optional[str] = None
    success: bool = True

# Helper function to sanitize data for JSON serialization
def sanitize_for_json(obj):
    """
    Ensure data is JSON serializable by converting problematic types.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items() if not callable(v)}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif callable(obj):
        return str(obj)  # Convert functions to their string representation
    elif hasattr(obj, '__dict__'):  # Handle custom objects
        return sanitize_for_json(obj.__dict__)
    else:
        return obj

# Functions to set and get components
def set_components(retriever: PineconeRetriever, responder: GeminiResponder):
    """Set the global component instances."""
    global _retriever_instance, _responder_instance
    _retriever_instance = retriever
    _responder_instance = responder
    
def get_retriever() -> PineconeRetriever:
    """Get the PineconeRetriever instance."""
    if _retriever_instance is None:
        raise ValueError("Retriever not initialized - call set_components first")
    return _retriever_instance

def get_responder() -> GeminiResponder:
    """Get the GeminiResponder instance."""
    if _responder_instance is None:
        raise ValueError("Responder not initialized - call set_components first")
    return _responder_instance

@router.post("/query", response_model=FastSearchResponse)
async def fast_search_query(
    request: FastSearchRequest,
    retriever: PineconeRetriever = Depends(get_retriever),
    responder: GeminiResponder = Depends(get_responder),
):
    """
    Process a Fast Search RAG query.
    
    This endpoint searches for relevant documents based on the query,
    then generates an answer based on the retrieved content.
    
    Parameters:
    - query: The search query
    - top_k: Number of documents to retrieve (1-20)
    - include_sources: Whether to include source documents in the response
    - include_metadata: Whether to include metadata in the response
    - use_fallbacks: Whether to use fallbacks in case of errors
    
    Returns:
    - An answer generated from the retrieved documents
    - Optionally, the source documents that informed the answer
    """
    try:
        logger.info(
            "Processing fast search query", 
            query=request.query,
            top_k=request.top_k
        )
        
        # Step 1: Retrieve relevant documents
        try:
            # Get raw documents
            retrieved_docs = retriever.semantic_search(request.query, top_k=request.top_k)
            
            # Sanitize documents to ensure they're JSON serializable
            retrieved_docs = sanitize_for_json(retrieved_docs)
            
            logger.info("Documents retrieved", count=len(retrieved_docs))
        except Exception as e:
            logger.error("Error retrieving documents", error=str(e))
            if request.use_fallbacks:
                return FastSearchResponse(
                    answer="I'm having trouble retrieving information at the moment. Please try again later.",
                    success=False,
                    error=f"Retrieval error: {str(e)}"
                )
            raise HTTPException(status_code=500, detail=str(e))
        
        # Step 2: Generate response
        try:
            answer = responder.generate_response(request.query, retrieved_docs)
            logger.info("Response generated")
        except Exception as e:
            logger.error("Error generating response", error=str(e))
            if request.use_fallbacks:
                return FastSearchResponse(
                    answer="I'm having trouble generating a response at the moment. Please try again later.",
                    success=False,
                    error=f"Response generation error: {str(e)}"
                )
            raise HTTPException(status_code=500, detail=str(e))
        
        # Step 3: Prepare response
        response = FastSearchResponse(answer=answer)
        
        # Include sources if requested
        if request.include_sources:
            sources = []
            for doc in retrieved_docs:
                # Make sure all values are JSON serializable
                sanitized_metadata = sanitize_for_json(doc.get("metadata", {})) if request.include_metadata else {}
                
                source = FastSearchSource(
                    text=doc.get("text", ""),
                    score=doc.get("score", 0.0),
                    metadata=sanitized_metadata
                )
                sources.append(source)
            response.sources = sources
        
        return response
    
    except Exception as e:
        logger.exception("Unexpected error in fast search query", error=str(e))
        return FastSearchResponse(
            answer="An unexpected error occurred while processing your query.",
            success=False,
            error=str(e)
        ) 