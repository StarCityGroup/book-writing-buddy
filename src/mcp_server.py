"""
MCP Server for Book Research.

Provides tools for Claude Code to interact with indexed research materials.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.indexer import ScrivenerIndexer, ZoteroIndexer
from src.skills import (
    AnnotationAggregator,
    CitationManager,
    FactExtractor,
    OutlineAnalyzer,
    ResearchGapDetector,
    SimilarityDetector,
)
from src.vectordb import create_client
from src.watcher import FileWatcherDaemon

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
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
            zotero_path=os.getenv("ZOTERO_PATH", "/mnt/zotero"),
            vectordb=self.vectordb,
            config=self.config,
        )

        self.scrivener_indexer = ScrivenerIndexer(
            scrivener_path=os.getenv("SCRIVENER_PATH", "/mnt/scrivener"),
            vectordb=self.vectordb,
            config=self.config,
        )

        # Initialize skills
        zotero_db_path = os.path.join(
            os.getenv("ZOTERO_PATH", "/mnt/zotero"), "zotero.sqlite"
        )
        scrivener_proj_path = os.getenv("SCRIVENER_PATH", "/mnt/scrivener")

        self.fact_extractor = FactExtractor()
        self.citation_manager = CitationManager(zotero_db_path)
        self.gap_detector = ResearchGapDetector(self.vectordb)
        self.outline_analyzer = OutlineAnalyzer(scrivener_proj_path, self.vectordb)
        self.annotation_aggregator = AnnotationAggregator(zotero_db_path)
        self.similarity_detector = SimilarityDetector(self.vectordb)

        # Initialize MCP server
        self.app = Server("book-research")
        self._register_handlers()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from files"""
        # Load default config
        default_config_path = Path("/app/config/default.json")
        with open(default_config_path) as f:
            config = json.load(f)

        # Overlay local config if exists
        local_config_path = Path("/app/config.local.json")
        if local_config_path.exists():
            with open(local_config_path) as f:
                local_config = json.load(f)
                config["project"] = local_config

        # Add environment variables
        config["vectordb_path"] = os.getenv("VECTORDB_PATH", "/data/vectordb")
        config["embedding"]["model"] = os.getenv(
            "EMBEDDING_MODEL", config["embedding"]["model"]
        )

        return config

    def _register_handlers(self):
        """Register MCP handlers"""

        @self.app.list_tools()
        async def list_tools() -> list:
            """List available tools"""
            return [
                Tool(
                    name="get_indexing_status",
                    description="Check what's been indexed and system status",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="search_research",
                    description="Semantic search across indexed research materials",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "chapter_number": {
                                "type": "integer",
                                "description": "Optional: filter by chapter",
                            },
                            "source_type": {
                                "type": "string",
                                "enum": ["zotero", "scrivener"],
                                "description": "Optional: filter by source",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 20,
                                "description": "Max results",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="prepare_chapter",
                    description="Gather all research materials for a specific chapter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number to prepare",
                            }
                        },
                        "required": ["chapter_number"],
                    },
                ),
                Tool(
                    name="analyze_theme_across_manuscript",
                    description="Find how a theme evolves across all chapters",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "theme": {
                                "type": "string",
                                "description": "Theme or topic to analyze",
                            }
                        },
                        "required": ["theme"],
                    },
                ),
                Tool(
                    name="find_cross_chapter_connections",
                    description="Discover connections between a chapter and other chapters",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number to find connections for",
                            }
                        },
                        "required": ["chapter_number"],
                    },
                ),
                Tool(
                    name="find_compelling_facts",
                    description="Find notable quotes, statistics, definitions, and case studies",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic to search for",
                            },
                            "fact_type": {
                                "type": "string",
                                "enum": [
                                    "quote",
                                    "statistic",
                                    "definition",
                                    "case_study",
                                    "any",
                                ],
                                "description": "Type of fact to find",
                            },
                            "chapter_number": {
                                "type": "integer",
                                "description": "Optional: filter by chapter",
                            },
                        },
                        "required": ["topic"],
                    },
                ),
                Tool(
                    name="get_citations_for_chapter",
                    description="Get formatted citations for sources in a chapter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "collection_id": {
                                "type": "integer",
                                "description": "Zotero collection ID",
                            },
                            "style": {
                                "type": "string",
                                "enum": ["chicago", "apa", "mla"],
                                "description": "Citation style (default: chicago)",
                            },
                        },
                        "required": ["collection_id"],
                    },
                ),
                Tool(
                    name="identify_research_gaps",
                    description="Identify areas needing more research",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Optional: specific chapter, or omit for all chapters",
                            }
                        },
                    },
                ),
                Tool(
                    name="get_chapter_outline",
                    description="Generate outline for a specific chapter from Scrivener",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number",
                            }
                        },
                        "required": ["chapter_number"],
                    },
                ),
                Tool(
                    name="analyze_manuscript_structure",
                    description="Analyze structure and length across entire manuscript",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_annotations",
                    description="Get Zotero annotations and notes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Optional: filter by chapter",
                            },
                            "source_id": {
                                "type": "integer",
                                "description": "Optional: filter by Zotero item ID",
                            },
                        },
                    },
                ),
                Tool(
                    name="find_similar_content",
                    description="Find content similar to given text",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to find similarities for",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Similarity threshold 0-1 (default: 0.85)",
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="detect_duplicates_in_chapter",
                    description="Detect near-duplicate content within a chapter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Similarity threshold 0-1 (default: 0.9)",
                            },
                        },
                        "required": ["chapter_number"],
                    },
                ),
            ]

        @self.app.call_tool()
        async def call_tool(name: str, arguments: Any) -> list:
            """Handle tool calls"""
            try:
                logger.info(
                    f"Tool call: name={name}, arguments type={type(arguments)}, arguments={arguments}"
                )

                if name == "get_indexing_status":
                    result = await self._get_indexing_status()
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "search_research":
                    result = await self._search_research(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "prepare_chapter":
                    result = await self._prepare_chapter(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "analyze_theme_across_manuscript":
                    result = await self._analyze_theme(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "find_cross_chapter_connections":
                    result = await self._find_connections(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "find_compelling_facts":
                    result = await self._find_facts(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_citations_for_chapter":
                    result = await self._get_citations(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "identify_research_gaps":
                    result = await self._identify_gaps(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_chapter_outline":
                    result = await self._get_outline(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "analyze_manuscript_structure":
                    result = await self._analyze_structure()
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "get_annotations":
                    result = await self._get_annotations(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "find_similar_content":
                    result = await self._find_similar(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif name == "detect_duplicates_in_chapter":
                    result = await self._detect_duplicates(**arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Tool call error: {e}", exc_info=True)
                raise

    async def _get_indexing_status(self) -> Dict[str, Any]:
        """Check what's been indexed and system status"""
        logger.info("Getting indexing status")

        collection_info = self.vectordb.get_collection_info()

        return {
            "total_chunks": collection_info["points_count"],
            "collection_status": collection_info["status"],
            "embedding_model": self.config["embedding"]["model"],
            "indexer_status": "running",
        }

    async def _search_research(
        self,
        query: str,
        chapter_number: Optional[int] = None,
        source_type: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Semantic search across indexed research materials"""
        logger.info(
            f"Searching research: query='{query}', chapter={chapter_number}, source={source_type}"
        )

        filters = {}
        if chapter_number:
            filters["chapter_number"] = chapter_number
        if source_type:
            filters["source_type"] = source_type

        results = self.vectordb.search(query, filters=filters, limit=limit)

        return {
            "query": query,
            "filters": filters,
            "count": len(results),
            "results": results,
        }

    async def _prepare_chapter(self, chapter_number: int) -> Dict[str, Any]:
        """Gather all research materials for a specific chapter"""
        logger.info(f"Preparing materials for chapter {chapter_number}")

        # Get collection info from Zotero
        collections = self.zotero_indexer.get_collections()
        chapter_collection = next(
            (c for c in collections if c["chapter_number"] == chapter_number), None
        )

        # Get Zotero materials
        zotero_results = self.vectordb.search(
            "",  # Empty query to get all
            filters={"chapter_number": chapter_number, "source_type": "zotero"},
            limit=100,
        )

        # Get Scrivener draft
        scrivener_results = self.vectordb.search(
            "",  # Empty query
            filters={"chapter_number": chapter_number, "source_type": "scrivener"},
            limit=50,
        )

        return {
            "chapter_number": chapter_number,
            "collection_name": chapter_collection["name"]
            if chapter_collection
            else None,
            "zotero_sources": len(zotero_results),
            "scrivener_sections": len(scrivener_results),
            "materials": {
                "zotero": zotero_results[:20],  # Top 20 chunks
                "scrivener": scrivener_results[:10],  # Top 10 sections
            },
        }

    async def _analyze_theme(self, theme: str) -> Dict[str, Any]:
        """Find how a theme evolves across all chapters"""
        logger.info(f"Analyzing theme: {theme}")

        # Search without filters to get all chapters
        all_results = self.vectordb.search(theme, limit=100)

        # Group by chapter
        by_chapter = {}
        for result in all_results:
            ch_num = result["metadata"].get("chapter_number")
            if ch_num:
                if ch_num not in by_chapter:
                    by_chapter[ch_num] = []
                by_chapter[ch_num].append(result)

        # Sort by chapter
        sorted_chapters = sorted(by_chapter.items())

        return {
            "theme": theme,
            "chapters_found": len(by_chapter),
            "total_mentions": len(all_results),
            "by_chapter": [
                {
                    "chapter": ch_num,
                    "occurrences": len(chunks),
                    "top_excerpts": [c["text"][:200] for c in chunks[:3]],
                }
                for ch_num, chunks in sorted_chapters
            ],
        }

    async def _find_connections(self, chapter_number: int) -> Dict[str, Any]:
        """Discover connections between a chapter and other chapters"""
        logger.info(f"Finding connections for chapter {chapter_number}")

        # Get representative chunks from target chapter
        chapter_chunks = self.vectordb.search(
            "",  # Empty query
            filters={"chapter_number": chapter_number},
            limit=10,
        )

        if not chapter_chunks:
            return {"error": f"No content found for chapter {chapter_number}"}

        # For each chunk, find similar chunks in OTHER chapters
        connections = {}
        for chunk in chapter_chunks[:5]:  # Use top 5 chunks as representatives
            similar = self.vectordb.search(chunk["text"], limit=20, score_threshold=0.6)

            for result in similar:
                other_ch = result["metadata"].get("chapter_number")
                if other_ch and other_ch != chapter_number:
                    if other_ch not in connections:
                        connections[other_ch] = []
                    connections[other_ch].append(
                        {
                            "similarity_score": result["score"],
                            "excerpt": result["text"][:150],
                        }
                    )

        # Sort by connection strength
        sorted_connections = sorted(
            connections.items(),
            key=lambda x: sum(c["similarity_score"] for c in x[1]) / len(x[1])
            if x[1]
            else 0,
            reverse=True,
        )

        return {
            "source_chapter": chapter_number,
            "connected_chapters": [
                {
                    "chapter": ch_num,
                    "connection_strength": sum(c["similarity_score"] for c in chunks)
                    / len(chunks),
                    "examples": chunks[:2],
                }
                for ch_num, chunks in sorted_connections[:10]
            ],
        }

    async def _find_facts(
        self, topic: str, fact_type: str = "any", chapter_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Find compelling facts, quotes, and statistics"""
        logger.info(
            f"Finding facts: topic='{topic}', type={fact_type}, chapter={chapter_number}"
        )

        # Search for topic
        filters = {}
        if chapter_number:
            filters["chapter_number"] = chapter_number

        results = self.vectordb.search(topic, filters=filters, limit=50)

        # Extract facts from results using fact extractor
        all_facts = []
        for result in results:
            text = result.get("text", "")
            metadata = result.get("metadata", {})

            facts = self.fact_extractor.extract_facts(text, metadata)

            # Filter by fact type if specified
            if fact_type != "any":
                facts = [f for f in facts if f["type"] == fact_type]

            all_facts.extend(facts)

        return {
            "topic": topic,
            "fact_type": fact_type,
            "chapter_number": chapter_number,
            "fact_count": len(all_facts),
            "facts": all_facts[:20],  # Limit to top 20
        }

    async def _get_citations(
        self, collection_id: int, style: str = "chicago"
    ) -> Dict[str, Any]:
        """Get formatted citations for a chapter"""
        logger.info(f"Getting citations: collection={collection_id}, style={style}")

        citations = await asyncio.to_thread(
            self.citation_manager.get_citations_for_chapter, collection_id, style
        )

        return {
            "collection_id": collection_id,
            "style": style,
            "citation_count": len(citations),
            "citations": citations,
        }

    async def _identify_gaps(
        self, chapter_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Identify research gaps"""
        logger.info(f"Identifying research gaps: chapter={chapter_number}")

        result = await asyncio.to_thread(
            self.gap_detector.identify_gaps, chapter_number
        )

        return result

    async def _get_outline(self, chapter_number: int) -> Dict[str, Any]:
        """Get chapter outline from Scrivener"""
        logger.info(f"Getting outline for chapter {chapter_number}")

        result = await asyncio.to_thread(
            self.outline_analyzer.get_chapter_outline, chapter_number
        )

        return result

    async def _analyze_structure(self) -> Dict[str, Any]:
        """Analyze manuscript structure"""
        logger.info("Analyzing manuscript structure")

        result = await asyncio.to_thread(
            self.outline_analyzer.analyze_manuscript_structure
        )

        return result

    async def _get_annotations(
        self, chapter_number: Optional[int] = None, source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get Zotero annotations"""
        logger.info(
            f"Getting annotations: chapter={chapter_number}, source={source_id}"
        )

        annotations = await asyncio.to_thread(
            self.annotation_aggregator.get_annotations, chapter_number, source_id
        )

        return {
            "chapter_number": chapter_number,
            "source_id": source_id,
            "annotation_count": len(annotations),
            "annotations": annotations,
        }

    async def _find_similar(self, text: str, threshold: float = 0.85) -> Dict[str, Any]:
        """Find similar content"""
        logger.info(f"Finding similar content: threshold={threshold}")

        similar = await asyncio.to_thread(
            self.similarity_detector.find_similar_content, text, threshold
        )

        return {
            "query_text": text[:200],
            "threshold": threshold,
            "matches": len(similar),
            "similar_content": similar,
        }

    async def _detect_duplicates(
        self, chapter_number: int, threshold: float = 0.9
    ) -> Dict[str, Any]:
        """Detect duplicates in chapter"""
        logger.info(
            f"Detecting duplicates: chapter={chapter_number}, threshold={threshold}"
        )

        result = await asyncio.to_thread(
            self.similarity_detector.detect_duplicates_in_chapter,
            chapter_number,
            threshold,
        )

        return result

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Book Research MCP Server")

        # Start file watcher in background
        watcher = FileWatcherDaemon(
            self.zotero_indexer, self.scrivener_indexer, self.config
        )

        # Run initial indexing in background (non-blocking)
        async def run_initial_indexing():
            logger.info("Performing initial indexing in background...")
            try:
                zotero_stats = await asyncio.to_thread(self.zotero_indexer.index_all)
                logger.info(f"Zotero indexing complete: {zotero_stats}")

                scrivener_stats = await asyncio.to_thread(
                    self.scrivener_indexer.index_all
                )
                logger.info(f"Scrivener indexing complete: {scrivener_stats}")
            except Exception as e:
                logger.error(f"Initial indexing failed: {e}")

        # Run watcher in background
        async def run_watcher():
            await asyncio.to_thread(watcher.start)

        # Start both background tasks
        indexing_task = asyncio.create_task(run_initial_indexing())
        watcher_task = asyncio.create_task(run_watcher())

        logger.info("MCP server ready (indexing continues in background)")

        # Run MCP server (this blocks until shutdown)
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.app.run(
                    read_stream, write_stream, self.app.create_initialization_options()
                )
        finally:
            # Cleanup (watcher.stop() may fail if stdio closed, ignore)
            try:
                watcher.stop()
            except Exception:
                pass

            # Cancel background tasks
            indexing_task.cancel()
            watcher_task.cancel()
            try:
                await indexing_task
            except asyncio.CancelledError:
                pass
            try:
                await watcher_task
            except asyncio.CancelledError:
                pass


async def main_daemon():
    """Run as daemon (container main process) - indexing and watching only"""
    server = BookResearchMCP()
    logger.info("Running as daemon (indexing + file watcher)")

    # Run initial indexing
    logger.info("Performing initial indexing...")
    try:
        zotero_stats = await asyncio.to_thread(server.zotero_indexer.index_all)
        logger.info(f"Zotero indexing complete: {zotero_stats}")

        scrivener_stats = await asyncio.to_thread(server.scrivener_indexer.index_all)
        logger.info(f"Scrivener indexing complete: {scrivener_stats}")
    except Exception as e:
        logger.error(f"Initial indexing failed: {e}")

    # Start file watcher (runs forever)
    logger.info("Starting file watcher...")
    watcher = FileWatcherDaemon(
        server.zotero_indexer, server.scrivener_indexer, server.config
    )

    try:
        watcher.start()  # Blocks forever
    except KeyboardInterrupt:
        watcher.stop()


async def main_mcp():
    """Run MCP server (called via docker exec) - now safe with Qdrant server mode"""
    server = BookResearchMCP()
    await server.run()


if __name__ == "__main__":
    import os

    # Check if MCP_MODE environment variable is set
    if os.getenv("MCP_MODE") == "stdio":
        # Running via docker exec for MCP queries
        asyncio.run(main_mcp())
    else:
        # Running as daemon (container main process)
        asyncio.run(main_daemon())
