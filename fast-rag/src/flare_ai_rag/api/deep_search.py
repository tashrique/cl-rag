from fastapi import APIRouter

from flare_ai_rag.retriever import PineconeRetriever
from flare_ai_rag.responder import GeminiResponder
from flare_ai_rag.api.routes.deep_search import router, set_components

class DeepSearchAPI:
    """
    API handler for Deep Search RAG functionality.
    
    This class initializes the Deep Search RAG API routes and sets up
    the dependencies for the retriever and responder.
    """
    
    def __init__(
        self,
        api_router: APIRouter,
        retriever: PineconeRetriever,
        responder: GeminiResponder,
    ) -> None:
        """
        Initialize the Deep Search API.
        
        Args:
            api_router: FastAPI router to attach routes to
            retriever: Instance of PineconeRetriever for document retrieval
            responder: Instance of GeminiResponder for response generation
        """
        self._router = api_router
        self.retriever = retriever
        self.responder = responder
        self._setup_routes()
        
    def _setup_routes(self) -> None:
        """
        Set up the API routes and provide component instances.
        """
        # Set the component instances for the router to use
        set_components(self.retriever, self.responder)
        
        # Include the router
        self._router.include_router(
            router,
            prefix="/deep-search",
            tags=["deep-search"],
        ) 