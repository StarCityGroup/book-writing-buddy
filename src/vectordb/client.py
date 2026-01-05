"""
Vector database client wrapper for Qdrant.

Handles embeddings storage, retrieval, and search operations.
"""

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()


class VectorDBClient:
    """Wrapper for Qdrant vector database with embedding generation"""

    def __init__(
        self,
        db_path: str = None,
        qdrant_url: str = None,
        collection_name: str = "book_research",
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_size: int = 384,
        model_cache_dir: str = None,
    ):
        """
        Initialize vector database client.

        Args:
            db_path: Path to Qdrant storage directory (for local mode)
            qdrant_url: URL to Qdrant server (e.g., "http://localhost:6333")
            collection_name: Name of the collection
            embedding_model: SentenceTransformer model name
            vector_size: Dimension of embeddings
            model_cache_dir: Path to local model cache (for offline operation)
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.model_cache_dir = model_cache_dir

        # Initialize Qdrant client (server mode or local mode)
        if qdrant_url:
            logger.info(f"Connecting to Qdrant server: {qdrant_url}")
            self.client = QdrantClient(url=qdrant_url)
        elif db_path:
            logger.info(f"Using Qdrant local storage: {db_path}")
            self.db_path = Path(db_path)
            self.client = QdrantClient(path=str(self.db_path))
        else:
            raise ValueError("Either db_path or qdrant_url must be provided")

        # Store embedding model name for lazy loading
        self.embedding_model_name = embedding_model
        self._embedder = None  # Lazy-loaded on first use
        self._embedder_lock = threading.Lock()  # Thread-safe lazy loading
        self._dimensions_verified = False

        # Create collection if it doesn't exist
        self._ensure_collection()

        # Note: embedding model will be loaded on first embed_texts() call
        # This avoids tokenizer parallelism warnings when processes fork after init

    @property
    def embedder(self):
        """Lazy-load the embedding model on first access (thread-safe)."""
        if self._embedder is None:
            with self._embedder_lock:
                # Double-check pattern to prevent race conditions
                if self._embedder is None:
                    if self.model_cache_dir:
                        logger.info(
                            f"Loading embedding model: {self.embedding_model_name} "
                            f"(from cache: {self.model_cache_dir})"
                        )
                        self._embedder = SentenceTransformer(
                            self.embedding_model_name,
                            cache_folder=self.model_cache_dir,
                        )
                    else:
                        logger.info(
                            f"Loading embedding model: {self.embedding_model_name}"
                        )
                        self._embedder = SentenceTransformer(self.embedding_model_name)

                    # Verify dimensions on first load
                    if not self._dimensions_verified:
                        self._verify_embedding_dimensions()
                        self._dimensions_verified = True

        return self._embedder

    def _verify_embedding_dimensions(self):
        """Verify that embedding model produces expected dimensions"""
        # Test with a sample text (use _embedder directly to avoid property recursion)
        test_embedding = self._embedder.encode(["test"], convert_to_numpy=True)
        actual_size = test_embedding.shape[1]

        if actual_size != self.vector_size:
            logger.error(
                f"CRITICAL: Embedding dimension mismatch! "
                f"Model '{self._embedder.get_sentence_embedding_dimension()}' produces {actual_size} dimensions "
                f"but vector_size is configured as {self.vector_size}. "
                f"Update config/default.json to match the model."
            )
            raise ValueError(
                f"Embedding model produces {actual_size} dimensions but "
                f"vector_size is configured as {self.vector_size}. "
                f"Common models: all-MiniLM-L6-v2=384, all-mpnet-base-v2=768"
            )

        logger.info(
            f"✓ Embedding dimensions verified: {actual_size} (model matches config)"
        )

    def _ensure_collection(self):
        """Create collection if it doesn't exist and validate vector dimensions"""
        try:
            collection = self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists")

            # Validate vector dimensions match
            existing_size = collection.config.params.vectors.size
            if existing_size != self.vector_size:
                logger.error(
                    f"CRITICAL: Vector dimension mismatch! "
                    f"Collection has {existing_size} dimensions but "
                    f"embedding model produces {self.vector_size} dimensions. "
                    f"This will cause errors. "
                    f"Delete the collection or use a different collection name."
                )
                raise ValueError(
                    f"Vector dimension mismatch: collection={existing_size}, "
                    f"model={self.vector_size}. "
                    f"Run: docker exec -it qdrant-qdrant-1 "
                    f"curl -X DELETE http://localhost:6333/collections/{self.collection_name}"
                )
        except Exception as e:
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(f"Creating collection '{self.collection_name}'")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size, distance=Distance.COSINE
                    ),
                )
            else:
                # Re-raise if it's a dimension mismatch error
                raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors
        """
        embeddings = self.embedder.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings.tolist()

    def index_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 32) -> int:
        """
        Index text chunks with embeddings.

        Args:
            chunks: List of dicts with 'text' and 'metadata' keys
            batch_size: Number of chunks to process at once

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # Extract texts
            texts = [chunk["text"] for chunk in batch]

            # Generate embeddings
            embeddings = self.embed_texts(texts)

            # Create points
            points = []
            for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                point_id = chunk.get("id") or self._generate_id(chunk)

                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={"text": chunk["text"], **chunk.get("metadata", {})},
                )
                points.append(point)

            # Upsert to Qdrant
            self.client.upsert(collection_name=self.collection_name, points=points)

            total_indexed += len(points)

            logger.debug(f"Indexed batch {i // batch_size + 1}: {len(points)} chunks")

        logger.info(f"Indexed {total_indexed} chunks total")
        return total_indexed

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks.

        Args:
            query: Search query text
            filters: Optional filters (e.g., {'chapter_number': 9})
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of results with text, metadata, and scores
        """
        # Generate query embedding
        query_embedding = self.embed_texts([query])[0]

        # Build filter if provided
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, list):
                    # Multiple values (OR condition)
                    for v in value:
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=v))
                        )
                else:
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )

            if conditions:
                qdrant_filter = Filter(must=conditions)

        # Search
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            score_threshold=score_threshold,
        ).points

        # Format results
        return [
            {
                "text": result.payload["text"],
                "score": result.score,
                "metadata": {k: v for k, v in result.payload.items() if k != "text"},
            }
            for result in results
        ]

    def query_by_metadata(
        self, filter_dict: Dict[str, Any], limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query points by metadata filters using scroll API (efficient for large result sets).

        Args:
            filter_dict: Metadata filters (e.g., {'source_type': 'zotero'})
            limit: Maximum number of results (None = all results)

        Returns:
            List of dicts with 'id', 'metadata', 'text'
        """
        # Build Qdrant filter
        conditions = []
        for key, value in filter_dict.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        qdrant_filter = Filter(must=conditions) if conditions else None

        # Use scroll API to retrieve ALL points efficiently
        results = []
        offset = None
        batch_size = 100  # Scroll in batches

        while True:
            batch, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qdrant_filter,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,  # Don't need vectors, just metadata
            )

            if not batch:
                break

            # Format results
            for point in batch:
                results.append(
                    {
                        "id": str(point.id),
                        "metadata": {
                            k: v for k, v in point.payload.items() if k != "text"
                        },
                        "text": point.payload.get("text", ""),
                    }
                )

            # Check if we've hit the limit
            if limit and len(results) >= limit:
                results = results[:limit]
                break

            # Continue scrolling
            if next_offset is None:
                break
            offset = next_offset

        logger.debug(
            f"Retrieved {len(results)} points with filter {filter_dict} "
            f"(limit={limit or 'unlimited'})"
        )
        return results

    def delete_by_filter(self, filters: Dict[str, Any]) -> bool:
        """
        Delete points matching filters.

        Args:
            filters: Filter conditions

        Returns:
            True if successful
        """
        conditions = []
        for key, value in filters.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        qdrant_filter = Filter(must=conditions)

        self.client.delete(
            collection_name=self.collection_name, points_selector=qdrant_filter
        )

        logger.info(f"Deleted points matching {filters}")
        return True

    def delete_by_source(self, source_type: str) -> bool:
        """
        Delete all points from a specific source.

        Args:
            source_type: Source type to delete ("zotero" or "scrivener")

        Returns:
            True if successful
        """
        return self.delete_by_filter({"source_type": source_type})

    def delete_by_scrivener_id(self, scrivener_id: str) -> int:
        """
        Delete all chunks for a specific Scrivener document UUID.

        Args:
            scrivener_id: Scrivener document UUID

        Returns:
            Number of points deleted (approximate, Qdrant doesn't return exact count)
        """
        # Count before deletion (for logging)
        before_count = len(
            self.query_by_metadata(
                {"source_type": "scrivener", "scrivener_id": scrivener_id}, limit=10000
            )
        )

        # Delete the points
        self.delete_by_filter(
            {"source_type": "scrivener", "scrivener_id": scrivener_id}
        )

        logger.info(f"Deleted ~{before_count} chunks for scrivener_id={scrivener_id}")
        return before_count

    def get_all_scrivener_ids(self) -> set:
        """
        Get all unique scrivener_id values from the vector database.

        Returns:
            Set of scrivener_id strings
        """
        # Query all scrivener documents (no limit)
        results = self.query_by_metadata({"source_type": "scrivener"}, limit=None)

        # Extract unique scrivener_ids
        scrivener_ids = {
            result["metadata"].get("scrivener_id")
            for result in results
            if result["metadata"].get("scrivener_id")
        }

        logger.debug(f"Found {len(scrivener_ids)} unique scrivener IDs in vector DB")
        return scrivener_ids

    def delete_orphaned_scrivener_docs(self, valid_ids: set) -> int:
        """
        Delete all Scrivener chunks whose IDs are not in the valid set.

        Args:
            valid_ids: Set of scrivener_id values that should exist

        Returns:
            Number of documents deleted
        """
        # Get all indexed IDs
        indexed_ids = self.get_all_scrivener_ids()

        # Find orphans (in DB but not in filesystem)
        orphaned_ids = indexed_ids - valid_ids

        if not orphaned_ids:
            logger.info("No orphaned Scrivener documents found")
            return 0

        logger.info(
            f"Found {len(orphaned_ids)} orphaned Scrivener documents, deleting..."
        )

        # Delete each orphaned document
        total_deleted = 0
        for scrivener_id in orphaned_ids:
            deleted = self.delete_by_scrivener_id(scrivener_id)
            total_deleted += deleted

        logger.info(f"Deleted {total_deleted} orphaned chunks total")
        return len(orphaned_ids)

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics"""
        info = self.client.get_collection(self.collection_name)

        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": info.status,
        }

    def _generate_id(self, chunk: Dict[str, Any]) -> str:
        """Generate unique UUID for a chunk"""
        import hashlib
        import uuid

        # Create deterministic UUID from metadata and text hash
        metadata = chunk.get("metadata", {})
        source = metadata.get("file_path", "unknown")
        text_hash = hashlib.md5(chunk["text"].encode()).hexdigest()

        # Generate UUID v5 (deterministic) from source + text hash
        namespace = uuid.NAMESPACE_DNS
        unique_string = f"{source}_{text_hash}"
        return str(uuid.uuid5(namespace, unique_string))

    def set_index_timestamp(self, source_type: str, timestamp: str) -> None:
        """Store index timestamp for a source type.

        Args:
            source_type: Either 'zotero' or 'scrivener'
            timestamp: ISO format timestamp string
        """
        import uuid

        # Use a deterministic UUID for metadata point
        # UUID v5 from DNS namespace and a fixed string
        metadata_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "book_research_metadata"))

        # Get existing metadata or create new
        try:
            existing = self.client.retrieve(
                collection_name=self.collection_name, ids=[metadata_id]
            )
            payload = existing[0].payload if existing else {}
        except Exception:
            payload = {}

        # Update timestamp
        key = f"last_indexed_{source_type}"
        payload[key] = timestamp

        # Create zero vector for metadata point
        zero_vector = [0.0] * self.vector_size

        # Upsert metadata point
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=metadata_id, vector=zero_vector, payload=payload)],
        )

        logger.info(f"Updated {source_type} index timestamp: {timestamp}")

    def get_index_timestamps(self) -> Dict[str, Optional[str]]:
        """Get last index timestamps for all source types.

        Returns:
            Dict with 'zotero' and 'scrivener' timestamp keys
        """
        import uuid

        # Use the same deterministic UUID
        metadata_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "book_research_metadata"))

        try:
            existing = self.client.retrieve(
                collection_name=self.collection_name, ids=[metadata_id]
            )
            if existing:
                payload = existing[0].payload
                return {
                    "zotero": payload.get("last_indexed_zotero"),
                    "scrivener": payload.get("last_indexed_scrivener"),
                }
        except Exception as e:
            logger.debug(f"No index timestamps found: {e}")

        return {"zotero": None, "scrivener": None}

    def backfill_timestamps_if_needed(self) -> bool:
        """Backfill timestamps for existing data if not set.

        Returns:
            True if timestamps were backfilled, False otherwise
        """
        from datetime import datetime, timezone

        # Check if we have data but no timestamps
        info = self.get_collection_info()
        points_count = info["points_count"]

        if points_count == 0:
            return False

        timestamps = self.get_index_timestamps()

        # If we have data but no timestamps, backfill them
        if timestamps["zotero"] is None and timestamps["scrivener"] is None:
            logger.info(
                f"Found {points_count} indexed chunks with no timestamps. "
                "Backfilling with current time..."
            )

            # Check what types of data we have by sampling
            try:
                # Sample some points to see what source types exist
                sample = self.client.scroll(
                    collection_name=self.collection_name, limit=100, with_payload=True
                )

                has_zotero = False
                has_scrivener = False

                for point in sample[0]:
                    source_type = point.payload.get("source_type")
                    if source_type == "zotero":
                        has_zotero = True
                    elif source_type == "scrivener":
                        has_scrivener = True

                # Set timestamps for source types that exist (use UTC)
                current_time = datetime.now(timezone.utc).isoformat()

                if has_zotero:
                    self.set_index_timestamp("zotero", current_time)
                    logger.info("✓ Backfilled Zotero timestamp")

                if has_scrivener:
                    self.set_index_timestamp("scrivener", current_time)
                    logger.info("✓ Backfilled Scrivener timestamp")

                return True

            except Exception as e:
                logger.warning(f"Could not backfill timestamps: {e}")
                return False

        return False


def create_client(config: Dict[str, Any]) -> VectorDBClient:
    """
    Factory function to create VectorDBClient from config.

    Args:
        config: Configuration dict with vectordb and embedding settings

    Returns:
        VectorDBClient instance
    """
    import os

    # Check if using Qdrant server or local storage
    qdrant_url = os.getenv("QDRANT_URL")

    # Get model cache directory for offline operation
    model_cache_dir = os.getenv("MODEL_CACHE_DIR")

    return VectorDBClient(
        db_path=config.get("vectordb_path") if not qdrant_url else None,
        qdrant_url=qdrant_url,
        collection_name=config["vectordb"]["collection_name"],
        embedding_model=config["embedding"]["model"],
        vector_size=config["embedding"]["vector_size"],
        model_cache_dir=model_cache_dir,
    )
