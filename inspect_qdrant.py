#!/usr/bin/env python3
"""Direct inspection of Qdrant database."""

import json
import os
from collections import Counter, defaultdict

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()


def inspect_qdrant():
    """Inspect Qdrant database directly."""
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = "book_research"

    print(f"Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url)

    # Get collection info
    try:
        collection = client.get_collection(collection_name)
        print(f"\n✓ Collection '{collection_name}' found")
        print(f"  Total points: {collection.points_count:,}")
        print(f"  Vector size: {collection.config.params.vectors.size}")
    except Exception as e:
        print(f"\n✗ Error getting collection: {e}")
        return

    # Sample MORE data to get accurate picture
    print(f"\nSampling 500 points...")
    try:
        sample, _ = client.scroll(
            collection_name=collection_name, limit=500, with_payload=True
        )

        # Analyze metadata
        source_types = Counter()
        chapter_numbers = Counter()
        has_chapter = 0
        no_chapter = 0
        doc_types = Counter()
        metadata_fields = set()

        for point in sample:
            payload = point.payload

            # Collect all metadata field names
            metadata_fields.update(payload.keys())

            # Source type
            source_type = payload.get("source_type", "unknown")
            source_types[source_type] += 1

            # Chapter number
            chapter_num = payload.get("chapter_number")
            if chapter_num is not None:
                chapter_numbers[chapter_num] += 1
                has_chapter += 1
            else:
                no_chapter += 1

            # Doc type (for Scrivener)
            doc_type = payload.get("doc_type")
            if doc_type:
                doc_types[doc_type] += 1

        print(f"\n{'='*60}")
        print("METADATA ANALYSIS (sample of 500 points)")
        print(f"{'='*60}")

        print(f"\n📊 Source Types:")
        for source_type, count in source_types.most_common():
            pct = (count / len(sample)) * 100
            print(f"  {source_type}: {count} ({pct:.1f}%)")

        print(f"\n📚 Chapter Metadata:")
        print(f"  Points WITH chapter_number: {has_chapter} ({(has_chapter/len(sample)*100):.1f}%)")
        print(f"  Points WITHOUT chapter_number: {no_chapter} ({(no_chapter/len(sample)*100):.1f}%)")

        if chapter_numbers:
            print(f"\n📖 Chapter Numbers Found:")
            for chapter_num in sorted(chapter_numbers.keys()):
                count = chapter_numbers[chapter_num]
                print(f"  Chapter {chapter_num}: {count} chunks")
        else:
            print("\n  ⚠️  NO CHAPTER NUMBERS FOUND IN SAMPLE")

        if doc_types:
            print(f"\n📝 Document Types (Scrivener):")
            for doc_type, count in doc_types.most_common():
                print(f"  {doc_type}: {count}")

        print(f"\n🏷️  All Metadata Fields Present:")
        for field in sorted(metadata_fields):
            print(f"  - {field}")

        # Sample a few actual payloads to see structure
        print(f"\n{'='*60}")
        print("SAMPLE PAYLOADS (first 3)")
        print(f"{'='*60}")
        for i, point in enumerate(sample[:3], 1):
            print(f"\n--- Point {i} ---")
            payload = point.payload.copy()
            # Truncate text for display
            if "text" in payload:
                text = payload["text"]
                payload["text"] = f"{text[:100]}..." if len(text) > 100 else text
            print(json.dumps(payload, indent=2, default=str))

        # Get ALL unique chapter numbers from entire collection (not just sample)
        print(f"\n{'='*60}")
        print("QUERYING ALL CHAPTER NUMBERS IN COLLECTION")
        print(f"{'='*60}")

        # Scroll through ALL points to get complete chapter list
        offset = None
        all_chapters = set()
        batch_count = 0

        while True:
            batch, offset = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=["chapter_number"],
            )

            if not batch:
                break

            batch_count += 1
            for point in batch:
                chapter_num = point.payload.get("chapter_number")
                if chapter_num is not None:
                    all_chapters.add(chapter_num)

            if offset is None:
                break

        print(f"\nScanned {batch_count * 100} points across entire collection")
        if all_chapters:
            print(f"\n✓ All unique chapter numbers in database:")
            print(f"  {sorted(all_chapters)}")
            print(f"\n  Total chapters with data: {len(all_chapters)}")
        else:
            print("\n⚠️  NO CHAPTER NUMBERS FOUND IN ENTIRE DATABASE")

    except Exception as e:
        print(f"\n✗ Error sampling data: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    inspect_qdrant()
