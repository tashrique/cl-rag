import google.api_core.exceptions
import pandas as pd
import structlog
import time
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from flare_ai_rag.ai import EmbeddingTaskType, GeminiEmbedding
from flare_ai_rag.retriever.config import RetrieverConfig

logger = structlog.get_logger(__name__)

# Maximum chunk size in characters for document splitting
# Reduced to avoid hitting Gemini's 10000 byte limit
MAX_CHUNK_SIZE = 5000


def _create_collection(
    client: QdrantClient, collection_name: str, vector_size: int
) -> None:
    """
    Creates a Qdrant collection with the given parameters.
    :param collection_name: Name of the collection.
    :param vector_size: Dimension of the vectors.
    """
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def _chunk_document(text: str, max_chunk_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    Split a document into smaller chunks to avoid size limits.
    
    :param text: The document text to split
    :param max_chunk_size: Maximum size of each chunk in characters
    :return: List of document chunks
    """
    logger.debug("Starting document chunking", text_length=len(text), max_chunk_size=max_chunk_size)
    
    # If the document is already small enough, return it as-is
    if len(text) <= max_chunk_size:
        return [text]
    
    chunks = []
    # Try to split at paragraph boundaries
    paragraphs = text.split("\n\n")
    current_chunk = ""
    
    for para in paragraphs:
        # If adding this paragraph would exceed the limit, save the current chunk and start a new one
        if len(current_chunk) + len(para) + 2 > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                logger.debug("Created chunk", chunk_length=len(current_chunk))
            
            # If a single paragraph is too large, split it into smaller pieces
            if len(para) > max_chunk_size:
                # Split at sentence boundaries if possible
                sentences = para.replace('. ', '.\n').split('\n')
                sub_chunk = ""
                
                for sentence in sentences:
                    if len(sub_chunk) + len(sentence) + 1 > max_chunk_size:
                        chunks.append(sub_chunk)
                        logger.debug("Created sub-chunk from large paragraph", chunk_length=len(sub_chunk))
                        sub_chunk = sentence
                    else:
                        if sub_chunk:
                            sub_chunk += " " + sentence
                        else:
                            sub_chunk = sentence
                
                if sub_chunk:
                    current_chunk = sub_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
        logger.debug("Created final chunk", chunk_length=len(current_chunk))
    
    logger.debug("Chunking completed", num_chunks=len(chunks))
    return chunks


def generate_collection(
    df_docs: pd.DataFrame,
    qdrant_client: QdrantClient,
    retriever_config: RetrieverConfig,
    embedding_client: GeminiEmbedding,
) -> None:
    """Routine for generating a Qdrant collection for a specific CSV file type."""
    _create_collection(
        qdrant_client, retriever_config.collection_name, retriever_config.vector_size
    )
    logger.info(
        "Created the collection.", collection_name=retriever_config.collection_name
    )

    points = []
    point_id = 1  # Start with ID 1
    processed_count = 0
    
    # Run only 100 documents for now
    # total_docs = 500  # For testing with limited documents
    total_docs = len(df_docs)  # Uncomment for full run
    logger.info(f"Starting to process {total_docs} documents")
    
    # Process only the first 100 documents
    # for _, row in df_docs.iloc[:total_docs].iterrows():
    for _, row in df_docs.iterrows():  # Uncomment for full run
        content = row["content"]
        file_name = row.get("file_name", "Unknown")
        metadata_str = row.get("meta_data", "")
        last_updated = row.get("last_updated", "")
        
        logger.debug(f"Processing document {processed_count+1}/{total_docs}", filename=file_name)
        
        # Parse metadata string into a dictionary of individual attributes
        metadata = {}
        if isinstance(metadata_str, str) and metadata_str:
            # Split by commas, but be careful with URLs that contain commas
            parts = []
            current_part = ""
            in_url = False
            
            # Handle URLs carefully when splitting by commas
            for char in metadata_str:
                if char == ',' and not in_url:
                    parts.append(current_part.strip())
                    current_part = ""
                else:
                    if char == ':' and "http" in current_part:
                        in_url = True
                    elif char == ' ' and in_url and current_part.endswith(','): 
                        in_url = False
                    current_part += char
                    
            if current_part:
                parts.append(current_part.strip())
                
            # If splitting didn't work well, try a simpler approach
            if not parts:
                parts = metadata_str.split(',')
            
            # Extract key-value pairs from each part
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    metadata[key.strip()] = value.strip()
        
        # Add the last_updated from the specific column
        if last_updated:
            metadata["last_updated"] = last_updated
        else:
            metadata["last_updated"] = ""

        if not isinstance(content, str):
            logger.warning(
                "Skipping document due to missing or invalid content.",
                filename=file_name,
            )
            continue

        # Initial attempt to embed the full document
        try:
            logger.debug("Attempting to embed full document", filename=file_name)
            embedding = embedding_client.embed_content(
                embedding_model=retriever_config.embedding_model,
                task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
                contents=content,
                title=str(file_name),
            )
            
            payload = {
                "filename": file_name,
                "metadata": metadata,
                "text": content,
            }

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )
            points.append(point)
            point_id += 1
            logger.debug("Successfully embedded full document", filename=file_name)
            
        except google.api_core.exceptions.InvalidArgument as e:
            error_msg = str(e)
            # If the error is due to size limit, try chunking the document
            if "400 Request payload size exceeds the limit" in error_msg:
                logger.info(
                    "Document exceeds size limit, applying chunking strategy.",
                    filename=file_name,
                )
                
                # Split the document into chunks
                try:
                    chunks = _chunk_document(content)
                    logger.info(
                        "Document split into chunks", 
                        filename=file_name, 
                        num_chunks=len(chunks)
                    )
                    
                    # Verify chunk sizes
                    for i, chunk in enumerate(chunks):
                        logger.debug(
                            f"Chunk {i+1} details", 
                            chunk_length=len(chunk), 
                            chunk_start=chunk[:50] if chunk else ""
                        )
                    
                    # Process each chunk
                    chunks_processed = 0
                    for i, chunk in enumerate(chunks):
                        logger.debug(f"Processing chunk {i+1}/{len(chunks)}", filename=file_name)
                        try:
                            start_time = time.time()
                            chunk_embedding = embedding_client.embed_content(
                                embedding_model=retriever_config.embedding_model,
                                task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
                                contents=chunk,
                                title=f"{file_name} [Part {i+1}/{len(chunks)}]",
                            )
                            embedding_time = time.time() - start_time
                            
                            logger.debug(
                                f"Embedding for chunk {i+1} completed", 
                                filename=file_name,
                                time_taken=f"{embedding_time:.2f}s"
                            )
                            
                            # Create a payload for this chunk
                            chunk_payload = {
                                "filename": f"{file_name} [Part {i+1}/{len(chunks)}]",
                                "metadata": metadata,
                                "text": chunk,
                                "is_chunk": True,
                                "chunk_index": i+1,
                                "total_chunks": len(chunks),
                                "parent_document": file_name,
                            }
                            
                            chunk_point = PointStruct(
                                id=point_id,
                                vector=chunk_embedding,
                                payload=chunk_payload,
                            )
                            points.append(chunk_point)
                            point_id += 1
                            chunks_processed += 1
                            logger.debug(f"Chunk {i+1} processing complete")
                        except Exception as chunk_error:
                            logger.exception(
                                "Error processing document chunk.",
                                filename=f"{file_name} [Part {i+1}/{len(chunks)}]",
                                error=str(chunk_error),
                            )
                            continue
                    
                    logger.info(
                        "Finished processing all chunks for document", 
                        filename=file_name,
                        chunks_processed=chunks_processed,
                        total_chunks=len(chunks)
                    )
                    
                except Exception as chunking_error:
                    logger.exception(
                        "Error during document chunking process",
                        filename=file_name,
                        error=str(chunking_error)
                    )
            else:
                # Log the full traceback for other InvalidArgument errors
                logger.exception(
                    "Error encoding document (InvalidArgument).",
                    filename=file_name,
                    error=error_msg
                )
                continue
        except Exception as general_error:
            # Log the full traceback for any other errors
            logger.exception(
                "Error encoding document (general).",
                filename=file_name,
                error=str(general_error),
            )
            continue
        
        processed_count += 1
        if processed_count % 10 == 0:  # More frequent updates for test run
        # if processed_count % 100 == 0:  # Uncomment for full run
            logger.info(f"Progress: {processed_count}/{total_docs} documents processed")
            
        # Batch insert points to avoid memory issues and provide checkpoints
        if len(points) >= 50:  # Smaller batch size for test run
        # if len(points) >= 100:  # Uncomment for full run
            try:
                logger.info(f"Inserting batch of {len(points)} points into Qdrant")
                qdrant_client.upsert(
                    collection_name=retriever_config.collection_name,
                    points=points,
                )
                logger.info("Batch insert successful")
                points = []  # Clear points after successful insertion
            except Exception as batch_error:
                logger.exception(
                    "Error during batch insertion",
                    error=str(batch_error),
                    num_points=len(points)
                )
                # Continue processing but keep the points for the final attempt

    # Insert any remaining points
    if points:
        try:
            logger.info(f"Inserting final batch of {len(points)} points into Qdrant")
            qdrant_client.upsert(
                collection_name=retriever_config.collection_name,
                points=points,
            )
            logger.info(
                "Collection generated and documents inserted into Qdrant successfully.",
                collection_name=retriever_config.collection_name,
                num_points=len(points),
            )
        except Exception as final_error:
            logger.exception(
                "Error during final batch insertion",
                error=str(final_error),
                num_points=len(points)
            )
    else:
        logger.warning("No valid documents found to insert.")
