#!/usr/bin/env python3
"""Diagnostic script to check Zotero database contents."""

import json
import os
import sqlite3
from pathlib import Path


def main():
    # Load config
    config_path = Path(__file__).parent / "config" / "default.json"
    with open(config_path) as f:
        config = json.load(f)

    # Get Zotero path from env or use default
    zotero_path = Path(os.getenv("ZOTERO_PATH", Path.home() / "Zotero"))
    db_path = zotero_path / "zotero.sqlite"
    storage_path = zotero_path / "storage"

    if not db_path.exists():
        print(f"❌ Zotero database not found at: {db_path}")
        return

    print(f"✓ Found Zotero database: {db_path}")
    print(f"✓ Storage path: {storage_path}")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all collections
    cursor.execute("""
        SELECT collectionID, collectionName, parentCollectionID
        FROM collections
        ORDER BY collectionName
    """)

    collections = cursor.fetchall()
    print(f"Found {len(collections)} collections\n")

    # Check each collection
    for coll_id, coll_name, parent_id in collections:
        print(f"Collection: {coll_name} (ID: {coll_id})")

        # Count items in collection
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM collectionItems
            WHERE collectionID = ?
        """,
            (coll_id,),
        )
        item_count = cursor.fetchone()[0]
        print(f"  Items: {item_count}")

        # Count items WITH attachments
        cursor.execute(
            """
            SELECT COUNT(DISTINCT i.itemID)
            FROM collectionItems ci
            JOIN items i ON ci.itemID = i.itemID
            JOIN itemAttachments ia ON i.itemID = ia.parentItemID
            WHERE ci.collectionID = ?
            AND ia.path IS NOT NULL
        """,
            (coll_id,),
        )
        items_with_attachments = cursor.fetchone()[0]
        print(f"  Items with attachments: {items_with_attachments}")

        # Get sample attachment paths
        cursor.execute(
            """
            SELECT i.itemID, iv.value as title, ia.path, ai.key, ia.contentType
            FROM collectionItems ci
            JOIN items i ON ci.itemID = i.itemID
            JOIN itemAttachments ia ON i.itemID = ia.parentItemID
            JOIN items ai ON ia.itemID = ai.itemID
            LEFT JOIN itemData id ON i.itemID = id.itemID AND id.fieldID = 1
            LEFT JOIN itemDataValues iv ON id.valueID = iv.valueID
            WHERE ci.collectionID = ?
            AND ia.path IS NOT NULL
            LIMIT 3
        """,
            (coll_id,),
        )

        sample_attachments = cursor.fetchall()
        if sample_attachments:
            print("  Sample attachments:")
            for item_id, title, path, key, content_type in sample_attachments:
                # Resolve path
                if path.startswith("storage:"):
                    filename = path.replace("storage:", "")
                    full_path = storage_path / key / filename
                    exists = "✓" if full_path.exists() else "❌"
                    print(f"    {exists} {title[:50]}...")
                    print(f"       Path: {path}")
                    print(f"       Key: {key}")
                    print(f"       Type: {content_type}")
                    print(f"       Resolved: {full_path}")
                    print(f"       Exists: {full_path.exists()}")
                else:
                    print(f"    - {title[:50]}... (absolute path: {path})")

        print()

    conn.close()


if __name__ == "__main__":
    main()
