"""
RAG Knowledge API Main Application Module

This module initializes and configures the FastAPI application for the RAG backend.
It sets up CORS middleware, loads configuration and data, and wires together the
Gemini-based Router, Retriever, and Responder components into a chat endpoint.
"""

import pandas as pd
import structlog
import uvicorn
import os
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pinecone import Pinecone

from flare_ai_rag.ai import GeminiEmbedding, GeminiProvider
from flare_ai_rag.api.routes import community_search
from flare_ai_rag.api import ChatRouter
from flare_ai_rag.api.community_search import CommunitySearchAPI
from flare_ai_rag.attestation import Vtpm
from flare_ai_rag.prompts import PromptService
from flare_ai_rag.responder import GeminiResponder, ResponderConfig
from flare_ai_rag.retriever import PineconeRetriever, RetrieverConfig, generate_collection
from flare_ai_rag.router import GeminiRouter, RouterConfig
from flare_ai_rag.settings import settings
from flare_ai_rag.utils import load_json

logger = structlog.get_logger(__name__)


def setup_router(input_config: dict) -> tuple[GeminiProvider, GeminiRouter]:
    """Initialize a Gemini Provider for routing."""
    # Setup router config
    router_model_config = input_config["router_model"]
    router_config = RouterConfig.load(router_model_config)

    # Setup Gemini client based on Router config
    # Older version used a system_instruction
    gemini_provider = GeminiProvider(
        api_key=settings.gemini_api_key, model=router_config.model.model_id
    )
    gemini_router = GeminiRouter(client=gemini_provider, config=router_config)

    return gemini_provider, gemini_router


def setup_retriever(
    pinecone_client: Pinecone,
    input_config: dict,
    df_docs: pd.DataFrame,
) -> PineconeRetriever:
    """Initialize the Pinecone retriever."""
    # Set up Pinecone config
    retriever_config = RetrieverConfig.load(input_config["retriever_config"])

    # Set up Gemini Embedding client
    embedding_client = GeminiEmbedding(settings.gemini_api_key)
    # (Re)generate pinecone collection
    generate_collection(
        df_docs,
        pinecone_client,
        retriever_config,
        embedding_client=embedding_client,
    )
    logger.info(
        "The Pinecone index has been generated.",
        collection_name=retriever_config.collection_name,
    )
    # Return retriever
    return PineconeRetriever(
        client=pinecone_client,
        retriever_config=retriever_config,
        embedding_client=embedding_client,
    )


def setup_pinecone(input_config: dict) -> Pinecone:
    """Initialize Pinecone client."""
    logger.info("Setting up Pinecone client...")
    retriever_config = RetrieverConfig.load(input_config["retriever_config"])
    
    # Use API key from settings if not explicitly provided in config
    api_key = retriever_config.pinecone_api_key or settings.pinecone_api_key
    if not api_key:
        raise ValueError("Pinecone API key must be set in either the retriever config or .env file")
    
    # Initialize Pinecone client
    pinecone_client = Pinecone(api_key=api_key)
    logger.info("Pinecone client has been set up.")

    return pinecone_client


def setup_responder(input_config: dict) -> GeminiResponder:
    """Initialize the responder."""
    # Set up Responder Config.
    responder_config = input_config["responder_model"]
    responder_config = ResponderConfig.load(responder_config)

    # Set up a new Gemini Provider based on Responder Config.
    gemini_provider = GeminiProvider(
        api_key=settings.gemini_api_key,
        model=responder_config.model.model_id,
        system_instruction=responder_config.system_prompt,
    )
    return GeminiResponder(client=gemini_provider, responder_config=responder_config)


def create_app() -> FastAPI:
    """Initialize the FastAPI app with all required components."""
    # Load documents from disk.
    logger.info("Loading documents...")
    df_docs = pd.read_csv(settings.data_path / "docs.csv")
    logger.info(
        "Documents have been loaded from disk.", num_documents=len(df_docs.index)
    )
    # Load config parameters.
    logger.info("Loading input parameters...")
    input_config = load_json(settings.input_path / "input_parameters.json")
    logger.info("Input parameters have been loaded.")

    # Set up Pinecone
    pinecone_client = setup_pinecone(input_config)

    # Set up the retriever.
    gemini_retriever = setup_retriever(pinecone_client, input_config, df_docs)
    logger.info("Retriever has been set up.")

    # Set up router
    _, gemini_router = setup_router(input_config)
    logger.info("Router has been set up.")

    # Set up the responder.
    gemini_responder = setup_responder(input_config)
    logger.info("Responder has been set up.")

    # Load Prompts
    prompt_service = PromptService()
    # Create API Routes
    logger.info("Creating API router...")
    api_router = APIRouter()
    attestation_manager = Vtpm(settings.simulate_attestation)

    # Create a ChatRouter
    api_chat_router = ChatRouter(
        router=api_router,
        ai=GeminiProvider(
            api_key=settings.gemini_api_key, 
            model=input_config["router_model"]["id"]
        ),
        query_router=gemini_router,
        retriever=gemini_retriever,
        responder=gemini_responder,
        attestation=attestation_manager,
        prompts=prompt_service,
    )
    
    # Create a Community Search API
    community_search_api = CommunitySearchAPI(
        api_router=api_router,
        retriever=gemini_retriever,
        responder=gemini_responder,
    )
    logger.info("Community Search API has been set up.")
    
    # Create FastAPI App
    app = FastAPI(
        title="Flare AI Community Search RAG System",
        description="Community-based RAG System for Flare AI hackathon",
    )
    # Include the API router with the community-search endpoints
    app.include_router(api_router, prefix="/api/routes/chat/community-search")

    # Setup CORS - ensure all origins are allowed for external API access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # Add health check
    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    logger.info("API server has been set up.")

    return app


def start() -> None:
    """Start the API server."""
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8004))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "flare_ai_rag.main:create_app",
        host=host,
        port=port,
        reload=False,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    start()
