"""
MCP Server for Book Research.

Provides tools for Claude Code to interact with indexed research materials.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
import structlog

from src.vectordb import create_client
from src.indexer import ZoteroIndexer, ScrivenerIndexer
from src.watcher import FileWatcherDaemon

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()


class BookResearchMCP:
    """MCP Server for book research"""

    def __init__(self):
        """Initialize MCP server"""
        self.config = self._load_config()
        self.vectordb = create_client(self.config)

        # Initialize indexers
        self.zotero_indexer = ZoteroIndexer(
            zotero_path=os.getenv('ZOTERO_PATH', '/mnt/zotero'),
            vectordb=self.vectordb,
            config=self.config
        )

        self.scrivener_indexer = ScrivenerIndexer(
            scrivener_path=os.getenv('SCRIVENER_PATH', '/mnt/scrivener'),
            vectordb=self.vectordb,
            config=self.config
        )

        # Initialize MCP server
        self.app = Server("book-research")
        self._register_tools()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from files"""
        # Load default config
        default_config_path = Path('/app/config/default.json')
        with open(default_config_path) as f:
            config = json.load(f)

        # Overlay local config if exists
        local_config_path = Path('/app/config.local.json')
        if local_config_path.exists():
            with open(local_config_path) as f:
                local_config = json.load(f)
                config['project'] = local_config

        # Add environment variables
        config['vectordb_path'] = os.getenv('VECTORDB_PATH', '/data/vectordb')
        config['embedding']['model'] = os.getenv('EMBEDDING_MODEL', config['embedding']['model'])

        return config

    def _register_tools(self):
        """Register MCP tools"""

        @self.app.list_tools()
        async def list_tools() -> list:
            """List available tools"""
            return [
                {
                    "name": "prepare_chapter",
                    "description": "Gather and synthesize all research materials for a chapter",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number to prepare"
                            }
                        },
                        "required": ["chapter_number"]
                    }
                },
                {
                    "name": "search_research",
                    "description": "Search indexed research materials with optional filters",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language search query"
                            },
                            "chapter": {
                                "type": "integer",
                                "description": "Filter to specific chapter (optional)"
                            },
                            "source_type": {
                                "type": "string",
                                "enum": ["zotero", "scrivener"],
                                "description": "Filter by source type (optional)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results to return",
                                "default": 20
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "analyze_theme_across_manuscript",
                    "description": "Search for a theme/concept across the entire manuscript",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "theme_query": {
                                "type": "string",
                                "description": "Theme or concept to analyze"
                            },
                            "part": {
                                "type": "string",
                                "description": "Filter to specific part (optional)"
                            }
                        },
                        "required": ["theme_query"]
                    }
                },
                {
                    "name": "find_cross_chapter_connections",
                    "description": "Find thematic connections between a chapter and others",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter to find connections for"
                            }
                        },
                        "required": ["chapter_number"]
                    }
                },
                {
                    "name": "get_indexing_status",
                    "description": "Check what's been indexed and system status",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]

        @self.app.call_tool()
        async def call_tool(name: str, arguments: dict) -> list:
            """Handle tool calls"""

            if name == "prepare_chapter":
                return await self._prepare_chapter(arguments["chapter_number"])
            elif name == "search_research":
                return await self._search_research(**arguments)
            elif name == "analyze_theme_across_manuscript":
                return await self._analyze_theme_across_manuscript(**arguments)
            elif name == "find_cross_chapter_connections":
                return await self._find_cross_chapter_connections(arguments["chapter_number"])
            elif name == "get_indexing_status":
                return await self._get_indexing_status()
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _prepare_chapter(self, chapter_number: int) -> list:
            """
            Gather and synthesize all research materials for a chapter.

            Args:
                chapter_number: Chapter number to prepare

            Returns:
                Dict with research chunks, context, and current draft
            """
            logger.info(f"Preparing chapter {chapter_number}")

            # Get chapter info from Zotero
            collections = self.zotero_indexer.get_collections()
            chapter_collection = next(
                (c for c in collections if c['chapter_number'] == chapter_number),
                None
            )

            # Multi-query approach for comprehensive coverage
            queries = [
                "important statistics facts data evidence",
                "case studies examples real-world applications",
                "compelling quotes arguments perspectives",
                "historical context background information"
            ]

            all_results = []
            for query_text in queries:
                results = self.vectordb.search(
                    query=query_text,
                    filters={'chapter_number': chapter_number},
                    limit=15,
                    score_threshold=0.7
                )
                all_results.extend(results)

            # Get adjacent chapters for context
            prev_results = self.vectordb.search(
                query="main themes",
                filters={'chapter_number': chapter_number - 1},
                limit=5
            ) if chapter_number > 1 else []

            next_results = self.vectordb.search(
                query="main themes",
                filters={'chapter_number': chapter_number + 1},
                limit=5
            ) if chapter_number < 30 else []

            # Get current Scrivener draft
            current_draft = self.scrivener_indexer.get_chapter_text(chapter_number)

            result = {
                'chapter_number': chapter_number,
                'chapter_title': chapter_collection['name'] if chapter_collection else f"Chapter {chapter_number}",
                'zotero_collection': chapter_collection['name'] if chapter_collection else None,
                'research_chunks': [
                    {
                        'text': r['text'],
                        'source_title': r['metadata'].get('title'),
                        'source_type': r['metadata']['source_type'],
                        'relevance_score': r['score']
                    }
                    for r in all_results
                ],
                'previous_chapter_context': prev_results,
                'next_chapter_context': next_results,
                'current_draft': current_draft,
                'total_sources': len(set(r['metadata'].get('file_path') for r in all_results if 'file_path' in r['metadata']))
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _search_research(
            query: str,
            chapter: Optional[int] = None,
            source_type: Optional[str] = None,
            limit: int = 20
        ) -> List[Dict[str, Any]]:
            """
            Search indexed research materials with optional filters.

            Args:
                query: Natural language search query
                chapter: Filter to specific chapter (optional)
                source_type: "zotero" | "scrivener" | None
                limit: Max results to return

            Returns:
                List of matching chunks with metadata
            """
            logger.info(f"Searching: {query}")

            filters = {}
            if chapter:
                filters['chapter_number'] = chapter
            if source_type:
                filters['source_type'] = source_type

            results = self.vectordb.search(
                query=query,
                filters=filters if filters else None,
                limit=limit,
                score_threshold=0.7
            )

            return [
                {
                    'text': r['text'],
                    'source': r['metadata'].get('title', r['metadata'].get('file_path', 'Unknown')),
                    'chapter': r['metadata'].get('chapter_number'),
                    'type': r['metadata']['source_type'],
                    'score': round(r['score'], 3)
                }
                for r in results
            ]

        @self.app.tool()
        async def analyze_theme_across_manuscript(
            theme_query: str,
            part: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Search for a theme/concept across the entire manuscript.

            Args:
                theme_query: Theme or concept to analyze
                part: Filter to "Part I", "Part II", or "Part III" (optional)

            Returns:
                Theme analysis with chunks grouped by chapter
            """
            logger.info(f"Analyzing theme: {theme_query}")

            # Determine chapter filter based on part
            chapter_filter = None
            if part:
                parts = self.config.get('project', {}).get('chapters', {}).get('structure', [])
                for p in parts:
                    if p['part'] == part:
                        chapter_filter = p['chapters']
                        break

            # Search across manuscript
            filters = {}
            if chapter_filter:
                # Qdrant doesn't support OR on same field easily,
                # so we'll search without filter and post-process
                pass

            results = self.vectordb.search(
                query=theme_query,
                filters=filters if filters else None,
                limit=100,
                score_threshold=0.65
            )

            # Group by chapter
            by_chapter = {}
            for r in results:
                ch = r['metadata'].get('chapter_number')
                if ch and (not chapter_filter or ch in chapter_filter):
                    if ch not in by_chapter:
                        by_chapter[ch] = {
                            'chapter_number': ch,
                            'chunks': []
                        }
                    by_chapter[ch]['chunks'].append({
                        'text': r['text'],
                        'source': r['metadata'].get('title', 'Unknown'),
                        'score': r['score']
                    })

            # Calculate coverage
            parts_structure = self.config.get('project', {}).get('chapters', {}).get('structure', [])
            coverage = {}
            for p in parts_structure:
                part_name = p['part']
                part_chapters = p['chapters']
                coverage[part_name] = sum(1 for ch in by_chapter if ch in part_chapters)

            return {
                'theme': theme_query,
                'total_mentions': len(results),
                'chapters_found': len(by_chapter),
                'by_chapter': dict(sorted(by_chapter.items())),
                'coverage': coverage
            }

        @self.app.tool()
        async def find_cross_chapter_connections(chapter_number: int) -> Dict[str, Any]:
            """
            Find thematic connections between this chapter and others.

            Args:
                chapter_number: Chapter to find connections for

            Returns:
                Dict of connected chapters with relevant excerpts
            """
            logger.info(f"Finding connections for chapter {chapter_number}")

            # Get this chapter's main content
            chapter_chunks = self.vectordb.search(
                query="",
                filters={'chapter_number': chapter_number},
                limit=50
            )

            if not chapter_chunks:
                return {
                    'source_chapter': chapter_number,
                    'connected_chapters': {},
                    'message': 'No content found for this chapter'
                }

            # Create a representative query from chapter content
            # (simplified - in production would use embedding averaging)
            chapter_text = " ".join([c['text'][:200] for c in chapter_chunks[:5]])

            # Search for similar content in other chapters
            similar = self.vectordb.search(
                query=chapter_text,
                filters=None,
                limit=30,
                score_threshold=0.75
            )

            # Group by chapter, excluding source chapter
            connections = {}
            for result in similar:
                ch = result['metadata'].get('chapter_number')
                if ch and ch != chapter_number:
                    if ch not in connections:
                        connections[ch] = []
                    connections[ch].append({
                        'text': result['text'],
                        'relevance': result['score']
                    })

            return {
                'source_chapter': chapter_number,
                'connected_chapters': connections
            }

        @self.app.tool()
        async def get_indexing_status() -> Dict[str, Any]:
            """Check what's been indexed and system status"""
            logger.info("Getting indexing status")

            collection_info = self.vectordb.get_collection_info()

            # Count by source type
            zotero_results = self.vectordb.search(
                query="",
                filters={'source_type': 'zotero'},
                limit=1
            )
            scrivener_results = self.vectordb.search(
                query="",
                filters={'source_type': 'scrivener'},
                limit=1
            )

            # Get indexed chapters
            all_results = self.vectordb.search(query="", filters=None, limit=1000)
            indexed_chapters = set(
                r['metadata'].get('chapter_number')
                for r in all_results
                if r['metadata'].get('chapter_number')
            )

            return {
                'total_chunks': collection_info['points_count'],
                'collection_status': collection_info['status'],
                'indexed_chapters': sorted(list(indexed_chapters)),
                'embedding_model': self.config['embedding']['model'],
                'indexer_status': 'running'
            }

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Book Research MCP Server")

        # Initial indexing
        logger.info("Performing initial indexing...")
        try:
            zotero_stats = self.zotero_indexer.index_all()
            logger.info(f"Zotero indexing: {zotero_stats}")

            scrivener_stats = self.scrivener_indexer.index_all()
            logger.info(f"Scrivener indexing: {scrivener_stats}")
        except Exception as e:
            logger.error(f"Initial indexing failed: {e}")

        # Start file watcher in background
        watcher = FileWatcherDaemon(
            self.zotero_indexer,
            self.scrivener_indexer,
            self.config
        )

        # Run watcher in background
        async def run_watcher():
            await asyncio.to_thread(watcher.start)

        watcher_task = asyncio.create_task(run_watcher())

        # Run MCP server
        async with stdio_server() as (read_stream, write_stream):
            await self.app.run(
                read_stream,
                write_stream,
                self.app.create_initialization_options()
            )

        # Cleanup
        watcher.stop()


async def main():
    """Main entry point"""
    server = BookResearchMCP()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
