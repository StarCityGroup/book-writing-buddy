#!/usr/bin/env python3
"""Search research materials in vector database."""

import json
import os
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer


def main():
    params = json.loads(sys.stdin.read())

    query = params.get("query", "")
    if not query:
        print(json.dumps({"error": "query parameter required"}))
        sys.exit(1)

    chapter_number = params.get("chapter_number")
    source_type = params.get("source_type")
    limit = params.get("limit", 20)

    # Connect to Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    # Generate query embedding
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vector = model.encode(query).tolist()

    # Build filter
    conditions = []
    if chapter_number:
        conditions.append(FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number)))
    if source_type:
        conditions.append(FieldCondition(key="source_type", match=MatchValue(value=source_type)))

    qdrant_filter = Filter(must=conditions) if conditions else None

    # Search
    results = client.query_points(
        collection_name="book_research",
        query=query_vector,
        query_filter=qdrant_filter,
        limit=limit,
        score_threshold=0.7
    ).points

    # Format output
    output = []
    for result in results:
        output.append({
            "text": result.payload.get("text", ""),
            "score": result.score,
            "source": result.payload.get("title", "Unknown"),
            "chapter": result.payload.get("chapter_number"),
            "type": result.payload.get("source_type"),
            "file_path": result.payload.get("file_path")
        })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
