#!/usr/bin/env python3
"""Find similar content in the research database."""

import json
import os
import sys

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


def main():
    params = json.loads(sys.stdin.read())

    text = params.get("text", "")
    if not text:
        print(json.dumps({"error": "text parameter required"}))
        sys.exit(1)

    threshold = params.get("threshold", 0.85)
    limit = params.get("limit", 10)

    # Connect to Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    # Generate embedding
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vector = model.encode(text).tolist()

    # Search
    results = client.query_points(
        collection_name="book_research",
        query=query_vector,
        limit=limit,
        score_threshold=threshold
    ).points

    # Format output
    output = []
    for result in results:
        payload = result.payload
        output.append({
            "text": payload.get("text", "")[:300],  # Preview only
            "similarity": result.score,
            "source": payload.get("title", "Unknown"),
            "chapter": payload.get("chapter_number"),
            "type": payload.get("source_type"),
            "warning": "High similarity detected" if result.score > 0.92 else None
        })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
