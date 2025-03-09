import os
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flare_ai_rag.retriever import PineconeRetriever
from flare_ai_rag.responder import GeminiResponder
from flare_ai_rag.api.routes import community_search
from flare_ai_rag.settings import settings

# Set up logging
logger = structlog.get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Community Search RAG API",
    description="API for community search retrieval-augmented generation",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
def init_components():
    logger.info("Initializing components")
    
    # Initialize Pinecone retriever
    try:
        retriever = PineconeRetriever(
            api_key=settings.pinecone_api_key,
            environment="gcp-starter", # TODO: Add to settings
            index_name=settings.pinecone_index_name,
            embedding_dimension=768 # TODO: Add to settings
        )
        logger.info("Pinecone retriever initialized")
    except Exception as e:
        logger.error(f"Error initializing Pinecone retriever: {str(e)}")
        raise
    
    # Initialize Gemini responder
    try:
        responder = GeminiResponder(
            api_key=settings.gemini_api_key,
            model="gemini-pro" # TODO: Add to settings
        )
        logger.info("Gemini responder initialized")
    except Exception as e:
        logger.error(f"Error initializing Gemini responder: {str(e)}")
        raise
    
    return retriever, responder

# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Application starting up")
        retriever, responder = init_components()
        
        # Set up the components for the API routes
        community_search.set_components(retriever, responder)
        
        # Include the direct endpoint for easier testing
        app.include_router(
            community_search.router, 
            tags=["direct-access"]
        )
        
        # Include the expected path for compatibility with the centralized server
        app.include_router(
            community_search.router, 
            prefix="/api/routes/chat/community-search",
            tags=["community-search"]
        )
        
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Community Search RAG API is running",
        "version": app.version,
        "endpoints": {
            "direct_query": "/query",
            "prefixed_query": "/api/routes/chat/community-search/query",
            "health": "/health"
        }
    }

# If this script is run directly, start the server
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run("main:app", host=settings.api_host, port=port, reload=True) 