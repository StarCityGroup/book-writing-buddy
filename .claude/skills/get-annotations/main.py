#!/usr/bin/env python3
"""Get Zotero annotations for a chapter."""

import json
import sqlite3
import sys
import re
from collections import defaultdict


def main():
    params = json.loads(sys.stdin.read())

    chapter_number = params.get("chapter_number")
    if not chapter_number:
        print(json.dumps({"error": "chapter_number required"}))
        sys.exit(1)

    # Connect to Zotero database
    db_path = "/Users/anthonytownsend/Zotero/zotero.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find chapter collection
    cursor.execute("""
        SELECT collectionID, collectionName
        FROM collections
        WHERE collectionName LIKE ?
    """, (f"{chapter_number}.%",))

    result = cursor.fetchone()
    if not result:
        print(json.dumps({"error": f"Chapter {chapter_number} not found"}))
        sys.exit(1)

    collection_id, collection_name = result

    # Get all items in this collection
    cursor.execute("""
        SELECT DISTINCT i.itemID
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        WHERE ci.collectionID = ?
    """, (collection_id,))

    item_ids = [row[0] for row in cursor.fetchall()]

    # Get annotations for these items
    annotations_by_source = defaultdict(list)

    for item_id in item_ids:
        # Get source title
        cursor.execute("""
            SELECT value
            FROM itemData id
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ? AND id.fieldID = 1
        """, (item_id,))

        title_result = cursor.fetchone()
        source_title = title_result[0] if title_result else "Untitled"

        # Get annotations
        cursor.execute("""
            SELECT annotationText, annotationComment, annotationType, annotationColor
            FROM itemAnnotations
            WHERE parentItemID = ?
        """, (item_id,))

        for text, comment, ann_type, color in cursor.fetchall():
            if text or comment:
                annotations_by_source[source_title].append({
                    "text": text,
                    "comment": comment,
                    "type": ann_type,
                    "color": color
                })

        # Get standalone notes
        cursor.execute("""
            SELECT note
            FROM itemNotes
            WHERE parentItemID = ? AND note IS NOT NULL
        """, (item_id,))

        for (note_html,) in cursor.fetchall():
            # Strip HTML
            note_text = re.sub(r'<[^>]+>', '', note_html)
            if note_text.strip():
                annotations_by_source[source_title].append({
                    "text": note_text,
                    "comment": None,
                    "type": "note",
                    "color": None
                })

    conn.close()

    # Format output
    output = {
        "chapter": chapter_number,
        "chapter_name": collection_name,
        "sources": []
    }

    for source_title, annotations in annotations_by_source.items():
        output["sources"].append({
            "title": source_title,
            "annotation_count": len(annotations),
            "annotations": annotations
        })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
