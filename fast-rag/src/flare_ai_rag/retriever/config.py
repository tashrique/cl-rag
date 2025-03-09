from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RetrieverConfig:
    """Configuration for the embedding model used in the retriever."""

    embedding_model: str
    collection_name: str
    vector_size: int
    host: Optional[str] = None
    port: Optional[int] = None
    db_type: str = "qdrant"  # "qdrant" or "pinecone"
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    pinecone_region: Optional[str] = "us-east-1"  # Default AWS region

    @staticmethod
    def load(retriever_config: dict[str, Any]) -> "RetrieverConfig":
        return RetrieverConfig(
            embedding_model=retriever_config["embedding_model"],
            collection_name=retriever_config["collection_name"],
            vector_size=retriever_config["vector_size"],
            host=retriever_config.get("host"),
            port=retriever_config.get("port"),
            db_type=retriever_config.get("db_type", "qdrant"),
            pinecone_api_key=retriever_config.get("pinecone_api_key"),
            pinecone_environment=retriever_config.get("pinecone_environment"),
            pinecone_region=retriever_config.get("pinecone_region", "us-east-1"),
        )
