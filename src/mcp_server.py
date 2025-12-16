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
        self._register_handlers()

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

    def _register_handlers(self):
        """Register MCP handlers"""

        @self.app.list_tools()
        async def list_tools() -> list:
            """List available tools"""
            return [
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

            if name == "get_indexing_status":
                result = await self._get_indexing_status()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _get_indexing_status(self) -> Dict[str, Any]:
        """Check what's been indexed and system status"""
        logger.info("Getting indexing status")

        collection_info = self.vectordb.get_collection_info()

        return {
            'total_chunks': collection_info['points_count'],
            'collection_status': collection_info['status'],
            'embedding_model': self.config['embedding']['model'],
            'indexer_status': 'running'
        }

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Book Research MCP Server")

        # Start file watcher in background
        watcher = FileWatcherDaemon(
            self.zotero_indexer,
            self.scrivener_indexer,
            self.config
        )

        # Run initial indexing in background (non-blocking)
        async def run_initial_indexing():
            logger.info("Performing initial indexing in background...")
            try:
                zotero_stats = await asyncio.to_thread(self.zotero_indexer.index_all)
                logger.info(f"Zotero indexing complete: {zotero_stats}")

                scrivener_stats = await asyncio.to_thread(self.scrivener_indexer.index_all)
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
                    read_stream,
                    write_stream,
                    self.app.create_initialization_options()
                )
        finally:
            # Cleanup (watcher.stop() may fail if stdio closed, ignore)
            try:
                watcher.stop()
            except:
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
    """Run as daemon (container main process) - just indexing and watching"""
    server = BookResearchMCP()
    logger.info("Running as daemon (no stdio - use 'docker exec' for MCP queries)")

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
        server.zotero_indexer,
        server.scrivener_indexer,
        server.config
    )

    try:
        watcher.start()  # Blocks forever
    except KeyboardInterrupt:
        watcher.stop()


async def main_mcp():
    """Run MCP server (called via docker exec)"""
    server = BookResearchMCP()
    await server.run()


if __name__ == "__main__":
    import sys
    import os

    # Check if MCP_MODE environment variable is set
    if os.getenv('MCP_MODE') == 'stdio':
        # Running via docker exec for MCP queries
        asyncio.run(main_mcp())
    else:
        # Running as daemon (container main process)
        asyncio.run(main_daemon())
