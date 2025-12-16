"""
Zotero database indexer.

Reads Zotero SQLite database, extracts attachments and notes,
and indexes them for semantic search.
"""

import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import structlog

from pypdf import PdfReader
from bs4 import BeautifulSoup

from .chunking import PDFChunker
from ..vectordb.client import VectorDBClient

logger = structlog.get_logger()


class ZoteroIndexer:
    """Index Zotero library for semantic search"""

    def __init__(
        self,
        zotero_path: str,
        vectordb: VectorDBClient,
        config: Dict[str, Any]
    ):
        """
        Initialize Zotero indexer.

        Args:
            zotero_path: Path to Zotero data directory
            vectordb: Vector database client
            config: Configuration dict
        """
        self.zotero_path = Path(zotero_path)
        self.db_path = self.zotero_path / "zotero.sqlite"
        self.storage_path = self.zotero_path / "storage"
        self.vectordb = vectordb
        self.config = config

        # Initialize chunker
        self.chunker = PDFChunker(
            target_size=config['embedding']['chunk_size'],
            min_size=config['chunking']['min_chunk_size'],
            max_size=config['chunking']['max_chunk_size'],
            overlap=config['embedding']['chunk_overlap']
        )

        # Get project-specific config
        self.root_collection = config.get('project', {}).get('zotero', {}).get('root_collection')
        self.chapter_pattern = config.get('project', {}).get('zotero', {}).get('chapter_pattern', r'^(\d+)\.')
        self.exclude_collections = config.get('project', {}).get('zotero', {}).get('exclude_collections', [])

    def get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections with chapter numbers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT collectionID, collectionName, parentCollectionID
            FROM collections
            ORDER BY collectionName
        """

        cursor.execute(query)
        collections = []

        for coll_id, name, parent_id in cursor.fetchall():
            # Skip excluded collections
            if name in self.exclude_collections:
                continue

            # Extract chapter number if matches pattern
            chapter_num = self._extract_chapter_number(name)

            collections.append({
                'id': coll_id,
                'name': name,
                'parent_id': parent_id,
                'chapter_number': chapter_num
            })

        conn.close()
        return collections

    def get_collection_items(self, collection_id: int) -> List[Dict[str, Any]]:
        """Get all items in a collection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT i.itemID, i.key, iv.value as title, ia.path
            FROM collectionItems ci
            JOIN items i ON ci.itemID = i.itemID
            LEFT JOIN itemData id ON i.itemID = id.itemID AND id.fieldID = 1
            LEFT JOIN itemDataValues iv ON id.valueID = iv.valueID
            LEFT JOIN itemAttachments ia ON i.itemID = ia.itemID
            WHERE ci.collectionID = ?
        """

        cursor.execute(query, (collection_id,))
        items = []

        for item_id, key, title, attachment_path in cursor.fetchall():
            items.append({
                'id': item_id,
                'key': key,
                'title': title or 'Untitled',
                'attachment_path': attachment_path
            })

        conn.close()
        return items

    def index_collection(self, collection_id: int) -> int:
        """
        Index all items in a collection.

        Args:
            collection_id: Zotero collection ID

        Returns:
            Number of chunks indexed
        """
        logger.info(f"Indexing collection {collection_id}")

        items = self.get_collection_items(collection_id)
        total_chunks = 0

        for item in items:
            try:
                chunks = self._index_item(item, collection_id)
                total_chunks += chunks
            except Exception as e:
                logger.error(f"Failed to index item {item['id']}: {e}")
                continue

        logger.info(f"Indexed {total_chunks} chunks from collection {collection_id}")
        return total_chunks

    def index_all(self) -> Dict[str, int]:
        """
        Index all collections.

        Returns:
            Dict with stats (collections_indexed, chunks_indexed)
        """
        collections = self.get_collections()
        stats = {
            'collections_indexed': 0,
            'chunks_indexed': 0
        }

        for collection in collections:
            if collection['chapter_number'] is not None:
                chunks = self.index_collection(collection['id'])
                stats['collections_indexed'] += 1
                stats['chunks_indexed'] += chunks

        return stats

    def _index_item(self, item: Dict[str, Any], collection_id: int) -> int:
        """Index a single Zotero item"""
        # Get collection info for metadata
        collections = self.get_collections()
        collection = next((c for c in collections if c['id'] == collection_id), None)

        metadata = {
            'source_type': 'zotero',
            'item_id': item['id'],
            'item_key': item['key'],
            'title': item['title'],
            'collection_id': collection_id,
            'collection_name': collection['name'] if collection else None,
            'chapter_number': collection['chapter_number'] if collection else None
        }

        # Extract text based on attachment type
        if item['attachment_path']:
            attachment_path = self._resolve_attachment_path(item['attachment_path'], item['key'])

            if attachment_path and attachment_path.exists():
                if attachment_path.suffix.lower() == '.pdf':
                    return self._index_pdf(attachment_path, metadata)
                elif attachment_path.suffix.lower() in ['.html', '.htm']:
                    return self._index_html(attachment_path, metadata)
                elif attachment_path.suffix.lower() == '.txt':
                    return self._index_text(attachment_path, metadata)

        return 0

    def _index_pdf(self, pdf_path: Path, metadata: Dict[str, Any]) -> int:
        """Extract text from PDF and index"""
        try:
            reader = PdfReader(str(pdf_path))

            pages = []
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text.strip():
                    pages.append({
                        'text': text,
                        'page_num': page_num
                    })

            # Add file path to metadata
            metadata['file_path'] = str(pdf_path)
            metadata['file_type'] = 'pdf'
            metadata['total_pages'] = len(reader.pages)

            # Chunk with page awareness
            chunks = self.chunker.chunk_with_pages(pages, metadata)

            # Convert to format expected by vectordb
            chunk_dicts = [
                {
                    'text': chunk.text,
                    'metadata': chunk.metadata
                }
                for chunk in chunks
            ]

            # Index
            return self.vectordb.index_chunks(chunk_dicts)

        except Exception as e:
            logger.error(f"Failed to extract PDF {pdf_path}: {e}")
            return 0

    def _index_html(self, html_path: Path, metadata: Dict[str, Any]) -> int:
        """Extract text from HTML and index"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style']):
                script.decompose()

            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text = '\n'.join(line for line in lines if line)

            metadata['file_path'] = str(html_path)
            metadata['file_type'] = 'html'

            # Chunk
            chunks = self.chunker.chunk(text, metadata)

            chunk_dicts = [
                {
                    'text': chunk.text,
                    'metadata': chunk.metadata
                }
                for chunk in chunks
            ]

            return self.vectordb.index_chunks(chunk_dicts)

        except Exception as e:
            logger.error(f"Failed to extract HTML {html_path}: {e}")
            return 0

    def _index_text(self, text_path: Path, metadata: Dict[str, Any]) -> int:
        """Index plain text file"""
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()

            metadata['file_path'] = str(text_path)
            metadata['file_type'] = 'text'

            chunks = self.chunker.chunk(text, metadata)

            chunk_dicts = [
                {
                    'text': chunk.text,
                    'metadata': chunk.metadata
                }
                for chunk in chunks
            ]

            return self.vectordb.index_chunks(chunk_dicts)

        except Exception as e:
            logger.error(f"Failed to read text {text_path}: {e}")
            return 0

    def _resolve_attachment_path(self, path: str, item_key: str) -> Optional[Path]:
        """Resolve Zotero attachment path"""
        if not path:
            return None

        # Zotero uses 'storage:' prefix for linked files
        if path.startswith('storage:'):
            filename = path.replace('storage:', '')
            return self.storage_path / item_key / filename

        # Absolute path
        return Path(path)

    def _extract_chapter_number(self, collection_name: str) -> Optional[int]:
        """Extract chapter number from collection name"""
        match = re.match(self.chapter_pattern, collection_name)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
        return None
