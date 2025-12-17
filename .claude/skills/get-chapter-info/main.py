#!/usr/bin/env python3
"""Get comprehensive chapter information."""

import json
import os
import sqlite3
import sys
from collections import defaultdict

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


def main():
    params = json.loads(sys.stdin.read())

    chapter_number = params.get("chapter_number")
    if not chapter_number:
        print(json.dumps({"error": "chapter_number required"}))
        sys.exit(1)

    # Get Zotero collection info
    db_path = "/Users/anthonytownsend/Zotero/zotero.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT collectionID, collectionName
        FROM collections
        WHERE collectionName LIKE ?
    """, (f"{chapter_number}.%",))

    result = cursor.fetchone()
    if not result:
        print(json.dumps({"error": f"Chapter {chapter_number} not found in Zotero"}))
        sys.exit(1)

    collection_id, collection_name = result

    # Count items in collection
    cursor.execute("""
        SELECT COUNT(DISTINCT itemID)
        FROM collectionItems
        WHERE collectionID = ?
    """, (collection_id,))

    item_count = cursor.fetchone()[0]
    conn.close()

    # Get vector DB stats
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    # Zotero content
    zotero_filter = Filter(must=[
        FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number)),
        FieldCondition(key="source_type", match=MatchValue(value="zotero"))
    ])

    zotero_points = client.scroll(
        collection_name="book_research",
        scroll_filter=zotero_filter,
        limit=1000
    )[0]

    # Scrivener content
    scrivener_filter = Filter(must=[
        FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number)),
        FieldCondition(key="source_type", match=MatchValue(value="scrivener"))
    ])

    scrivener_points = client.scroll(
        collection_name="book_research",
        scroll_filter=scrivener_filter,
        limit=1000
    )[0]

    # Analyze Scrivener structure
    sections = defaultdict(lambda: {"chunks": 0, "words": 0})
    for point in scrivener_points:
        file_path = point.payload.get("file_path", "unknown")
        text = point.payload.get("text", "")
        sections[file_path]["chunks"] += 1
        sections[file_path]["words"] += len(text.split())

    # Format output
    output = {
        "chapter_number": chapter_number,
        "collection_name": collection_name,
        "zotero": {
            "collection_id": collection_id,
            "source_count": item_count,
            "indexed_chunks": len(zotero_points)
        },
        "scrivener": {
            "indexed_chunks": len(scrivener_points),
            "section_count": len(sections),
            "total_words": sum(s["words"] for s in sections.values()),
            "sections": [
                {
                    "file": file_path,
                    "chunks": data["chunks"],
                    "words": data["words"]
                }
                for file_path, data in sorted(sections.items())
            ]
        },
        "status": {
            "has_research": len(zotero_points) > 0,
            "has_draft": len(scrivener_points) > 0,
            "research_density": "good" if len(zotero_points) > 20 else "sparse"
        }
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
