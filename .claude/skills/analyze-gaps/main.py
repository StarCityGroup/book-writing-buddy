#!/usr/bin/env python3
"""Analyze research gaps in indexed content."""

import json
import os
import sys
from collections import defaultdict

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


def analyze_chapter(client, chapter_number):
    """Analyze gaps for a specific chapter."""
    # Get all chunks for this chapter
    zotero_filter = Filter(must=[
        FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number)),
        FieldCondition(key="source_type", match=MatchValue(value="zotero"))
    ])

    scrivener_filter = Filter(must=[
        FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number)),
        FieldCondition(key="source_type", match=MatchValue(value="scrivener"))
    ])

    zotero_results = client.scroll(
        collection_name="book_research",
        scroll_filter=zotero_filter,
        limit=1000
    )[0]

    scrivener_results = client.scroll(
        collection_name="book_research",
        scroll_filter=scrivener_filter,
        limit=1000
    )[0]

    # Count unique sources
    unique_sources = set()
    for point in zotero_results:
        item_id = point.payload.get("item_id")
        if item_id:
            unique_sources.add(item_id)

    # Identify gaps
    gaps = []

    if len(unique_sources) < 5:
        gaps.append({
            "type": "low_source_count",
            "severity": "high",
            "message": f"Only {len(unique_sources)} unique sources. Consider adding more research materials."
        })

    if len(zotero_results) < 20:
        gaps.append({
            "type": "sparse_coverage",
            "severity": "medium",
            "message": f"Only {len(zotero_results)} text chunks indexed. May need more detailed sources."
        })

    if len(scrivener_results) == 0:
        gaps.append({
            "type": "no_draft",
            "severity": "low",
            "message": "No Scrivener draft found for this chapter."
        })

    return {
        "chapter": chapter_number,
        "unique_sources": len(unique_sources),
        "zotero_chunks": len(zotero_results),
        "scrivener_chunks": len(scrivener_results),
        "gaps": gaps,
        "status": "needs_attention" if gaps else "well_researched"
    }


def analyze_manuscript(client):
    """Analyze gaps across entire manuscript."""
    # Get all points
    all_points = client.scroll(
        collection_name="book_research",
        limit=10000
    )[0]

    # Group by chapter
    chapter_stats = defaultdict(lambda: {"zotero": 0, "scrivener": 0, "sources": set()})

    for point in all_points:
        payload = point.payload
        ch_num = payload.get("chapter_number")
        source_type = payload.get("source_type")
        item_id = payload.get("item_id")

        if ch_num:
            if source_type == "zotero":
                chapter_stats[ch_num]["zotero"] += 1
                if item_id:
                    chapter_stats[ch_num]["sources"].add(item_id)
            elif source_type == "scrivener":
                chapter_stats[ch_num]["scrivener"] += 1

    if not chapter_stats:
        return {"error": "No indexed data found"}

    # Calculate averages
    chapters = list(chapter_stats.keys())
    avg_sources = sum(len(s["sources"]) for s in chapter_stats.values()) / len(chapters)
    avg_chunks = sum(s["zotero"] for s in chapter_stats.values()) / len(chapters)

    # Find weak chapters
    weak_chapters = []
    for ch_num, stats in chapter_stats.items():
        source_count = len(stats["sources"])
        chunk_count = stats["zotero"]

        if source_count < avg_sources * 0.5:
            weak_chapters.append({
                "chapter": ch_num,
                "sources": source_count,
                "severity": "high",
                "reason": f"Only {source_count} sources (avg: {round(avg_sources, 1)})"
            })
        elif chunk_count < avg_chunks * 0.5:
            weak_chapters.append({
                "chapter": ch_num,
                "chunks": chunk_count,
                "severity": "medium",
                "reason": f"Low coverage: {chunk_count} chunks (avg: {round(avg_chunks, 1)})"
            })

    return {
        "total_chapters": len(chapters),
        "avg_sources_per_chapter": round(avg_sources, 1),
        "avg_chunks_per_chapter": round(avg_chunks, 1),
        "weak_chapters": sorted(weak_chapters, key=lambda x: x["chapter"]),
        "status": "has_gaps" if weak_chapters else "well_balanced"
    }


def main():
    params = json.loads(sys.stdin.read())

    chapter_number = params.get("chapter_number")

    # Connect to Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    if chapter_number:
        result = analyze_chapter(client, chapter_number)
    else:
        result = analyze_manuscript(client)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
