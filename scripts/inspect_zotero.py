#!/usr/bin/env python3
"""Direct inspection of Zotero database."""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def inspect_zotero():
    """Inspect Zotero database to see what collections and items exist."""
    zotero_path = os.getenv("ZOTERO_PATH")
    if not zotero_path:
        print("ZOTERO_PATH not set in .env")
        return

    db_path = Path(zotero_path) / "zotero.sqlite"
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    print(f"Connecting to Zotero database at {db_path}...")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all collections with "chapter" or numbers in the name
        print("\n" + "=" * 80)
        print("ZOTERO COLLECTIONS (filtered for chapters)")
        print("=" * 80)

        query = """
            SELECT
                collectionID,
                collectionName,
                parentCollectionID
            FROM collections
            WHERE collectionName LIKE '%chapter%'
               OR collectionName LIKE '%5%'
               OR collectionName LIKE '%9%'
            ORDER BY collectionName
        """

        cursor.execute(query)
        collections = cursor.fetchall()

        collection_map = {}
        for coll in collections:
            collection_map[coll["collectionID"]] = coll["collectionName"]
            parent = coll["parentCollectionID"]
            parent_name = (
                collection_map.get(parent, f"Parent {parent}") if parent else "ROOT"
            )
            print(f"\n[{coll['collectionID']}] {coll['collectionName']}")
            print(f"    Parent: {parent_name}")

        # Now get items in Chapter 5 and Chapter 9 collections
        for chapter_num in [5, 9]:
            print("\n" + "=" * 80)
            print(f"CHAPTER {chapter_num} - ITEMS AND FILES")
            print("=" * 80)

            # Find collection(s) matching this chapter
            query = """
                SELECT collectionID, collectionName
                FROM collections
                WHERE collectionName LIKE ?
            """
            cursor.execute(query, (f"%{chapter_num}%",))
            chapter_collections = cursor.fetchall()

            if not chapter_collections:
                print(f"\n⚠️  No collection found matching chapter {chapter_num}")
                continue

            for coll in chapter_collections:
                coll_id = coll["collectionID"]
                coll_name = coll["collectionName"]

                print(f"\nCollection: [{coll_id}] {coll_name}")
                print("-" * 80)

                # Get items in this collection
                query = """
                    SELECT DISTINCT
                        i.itemID,
                        i.itemTypeID,
                        it.typeName,
                        COALESCE(idv.value, 'Untitled') as title,
                        i.key
                    FROM collectionItems ci
                    JOIN items i ON ci.itemID = i.itemID
                    JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                    LEFT JOIN itemData id ON i.itemID = id.itemID
                        AND id.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
                    LEFT JOIN itemDataValues idv ON id.valueID = idv.valueID
                    WHERE ci.collectionID = ?
                    ORDER BY i.itemID
                """

                cursor.execute(query, (coll_id,))
                items = cursor.fetchall()

                print(f"\nTotal items in collection: {len(items)}")

                for item in items:
                    item_id = item["itemID"]
                    item_type = item["typeName"]
                    title = item["title"]
                    key = item["key"]

                    print(f"\n  [{item_id}] {title}")
                    print(f"    Type: {item_type}")
                    print(f"    Key: {key}")

                    # Get attachments for this item
                    attach_query = """
                        SELECT
                            ia.itemID as attachmentID,
                            ia.path,
                            ia.contentType
                        FROM itemAttachments ia
                        WHERE ia.parentItemID = ?
                    """

                    cursor.execute(attach_query, (item_id,))
                    attachments = cursor.fetchall()

                    if attachments:
                        print(f"    Attachments: {len(attachments)}")
                        for att in attachments:
                            att_id = att["attachmentID"]
                            path = att["path"]
                            content_type = att["contentType"]

                            # Resolve the actual file path
                            if path:
                                if path.startswith("storage:"):
                                    # storage:ABCD1234/file.pdf
                                    storage_key = path.split(":")[1].split("/")[0]
                                    filename = (
                                        path.split("/")[1] if "/" in path else "file"
                                    )
                                    full_path = (
                                        Path(zotero_path)
                                        / "storage"
                                        / storage_key
                                        / filename
                                    )
                                else:
                                    full_path = Path(path)

                                exists = full_path.exists() if full_path else False
                                size = full_path.stat().st_size if exists else 0
                                size_mb = size / (1024 * 1024)

                                print(f"      [{att_id}] {content_type}")
                                print(f"        Path: {path}")
                                print(
                                    f"        Exists: {'✓ YES' if exists else '✗ NO'}"
                                )
                                if exists:
                                    print(f"        Size: {size_mb:.2f} MB")
                    else:
                        print("    ⚠️  No attachments found")

                    # Check if this item has annotations
                    annot_query = """
                        SELECT COUNT(*) as count
                        FROM itemAnnotations
                        WHERE parentItemID = ?
                    """
                    cursor.execute(annot_query, (item_id,))
                    annot_count = cursor.fetchone()["count"]
                    if annot_count > 0:
                        print(f"    📝 Annotations: {annot_count}")

        conn.close()

    except sqlite3.Error as e:
        print(f"\n✗ Database error: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    inspect_zotero()
