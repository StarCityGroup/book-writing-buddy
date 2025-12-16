# Book Research MCP

A Model Context Protocol (MCP) server that indexes your Zotero research library and Scrivener manuscript, providing intelligent search and analysis through Claude Code CLI.

## What It Does

- **Monitors** your Zotero and Scrivener files for changes
- **Indexes** all documents with embeddings for semantic search
- **Provides** natural language queries through Claude Code
- **Analyzes** themes, connections, and research gaps across your manuscript

## Use Cases

- 📚 **Chapter Preparation**: "Gather all materials for chapter 9"
- 🔍 **Theme Analysis**: "Is resilience a common theme? Show me how it evolves"
- 🔗 **Cross-References**: "Find connections between chapters 5 and 12"
- 📊 **Research Gaps**: "Which chapters need more sources?"

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Zotero with local database
- Scrivener project (or any structured writing project)
- Claude Code CLI

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/book-research-mcp.git
cd book-research-mcp

# Run interactive setup (creates .env and config.local.json)
python scripts/setup.py

# Start the service
docker compose up --build -d

# Check status
docker compose logs -f
```

### Test It

```bash
# From the project directory
claude
```

The MCP server is configured in `.claude/config.json` (project-specific, no global config needed).

Then try:
```
> Get indexing status
> Prepare materials for chapter 1
> Is "adaptation" a common theme across the manuscript?
```

## Architecture

```
Docker Container
├── File Watcher (watchdog)
│   └── Monitors Zotero & Scrivener for changes
├── Indexing Pipeline
│   ├── Text extraction (PDF, RTF, HTML)
│   ├── Semantic chunking (preserves context)
│   └── Embedding generation (all-MiniLM-L6-v2)
├── Vector Database (Qdrant)
│   └── Stores 384-dimensional embeddings with metadata
└── MCP Server (stdio interface)
    └── Exposes 5 tools to Claude Code
```

### How It Works

1. **Initial Setup**: You run `setup.py` to configure paths
2. **Indexing**: Docker container starts, reads all Zotero PDFs and Scrivener files
3. **Chunking**: Documents split into ~500-character semantic chunks
4. **Embedding**: Each chunk gets a 384-dimensional vector (all-MiniLM-L6-v2)
5. **Storage**: Vectors stored in Qdrant with rich metadata (chapter, source, page)
6. **Watching**: File watcher monitors for changes and re-indexes automatically
7. **Querying**: You ask Claude Code questions, it searches the vector DB, returns relevant chunks
8. **Analysis**: Claude synthesizes the retrieved chunks into insights

## Configuration

### Environment Variables (`.env`)

Created by `setup.py`, contains your personal paths:

```bash
ZOTERO_DATA_PATH=/path/to/your/Zotero
SCRIVENER_PROJECT_PATH=/path/to/your/Project.scriv
EMBEDDING_MODEL=all-mpnet-base-v2
VECTORDB_PATH=./data/vectordb
DEBUG=false
```

### Project Settings (`config.local.json`)

Your book-specific configuration:

```json
{
  "project": {
    "name": "My Book Title",
    "author": "Your Name"
  },
  "zotero": {
    "root_collection": "My Book",
    "chapter_pattern": "^(\\d+)\\.",
    "exclude_collections": ["Archive", "_incoming"]
  },
  "scrivener": {
    "draft_folder": "Manuscript",
    "research_folder": "Research"
  },
  "chapters": {
    "structure": [
      {"part": "Part I", "chapters": [1, 2, 3]},
      {"part": "Part II", "chapters": [4, 5, 6]}
    ]
  }
}
```

### Default Settings (`config/default.json`)

Chunking and embedding parameters (committed to repo):

```json
{
  "embedding": {
    "model": "all-MiniLM-L6-v2",
    "chunk_size": 500,
    "chunk_overlap": 100,
    "vector_size": 384
  },
  "chunking": {
    "min_chunk_size": 200,
    "max_chunk_size": 800
  }
}
```

## MCP Tools Provided

| Tool | Purpose | Example |
|------|---------|---------|
| `prepare_chapter(num)` | Gather all research for a chapter | "Prepare materials for chapter 9" |
| `search_research(query, filters)` | Semantic search across materials | "Find examples of infrastructure failures" |
| `analyze_theme_across_manuscript(theme)` | Find theme evolution | "How does resilience evolve across parts?" |
| `find_cross_chapter_connections(num)` | Discover related content | "What connects chapter 5 to other chapters?" |
| `get_indexing_status()` | Check system health | "Get indexing status" |

## Usage Examples

### Chapter Preparation

```
You: Prepare materials for chapter 9

Claude: I've gathered materials from 23 sources in your Zotero
collection "9. underground cables". Here are the key themes...

**Key Themes:**
1. Infrastructure resilience in coastal cities
2. Telecommunications vulnerability to flooding
3. Historical failures: Hurricane Sandy, Thailand floods

**Compelling Facts:**
- "90% of undersea cables pass through just 10 chokepoints" (TeleGeography 2023)
- NYC lost 14 cell towers in Sandy

**Cross-Chapter Connections:**
- Chapter 5: early warning systems (critical infrastructure theme)
- Chapter 15: economic impacts ($50B in cable failure losses)

**Current Draft:** 3,200 words in Scrivener. Gaps: need more on submarine cable economics
```

### Thematic Analysis

```
You: Is "climate adaptation" discussed across the whole manuscript?

Claude: Yes, it appears in 19 of 27 chapters. Here's the evolution:

**Part I (Chapters 1-4):** Resilience framed as individual/community adaptation
**Part II (Chapters 5-23):** Shifts to infrastructure and systems resilience
**Part III (Chapters 24-27):** Synthesizes into institutional resilience

The framing changes in Chapter 12 when you introduce...
```

### Targeted Search

```
You: Find examples of infrastructure failures in Asia

Claude: Found 8 relevant examples:

1. "Thailand floods 2011 disrupted global hard drive supply..." (Chapter 9, PDF p.47)
2. "Tokyo's adaptive infrastructure reduced flood damage by 60%..." (Chapter 11)
...
```

## Customization

### Change Embedding Model

Edit `.env`:
```bash
# Fast, good quality (default)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Best quality (slower, larger)
EMBEDDING_MODEL=all-mpnet-base-v2

# Multi-language
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

Then rebuild: `docker compose up --build -d`

### Adjust Chunk Sizes

Edit `config/default.json`:
```json
{
  "embedding": {
    "chunk_size": 600,
    "chunk_overlap": 150
  }
}
```

Larger chunks = more context per result
Smaller chunks = more precise matching

### Chapter Structure

Edit `config.local.json` to define your book's structure:
```json
{
  "chapters": {
    "structure": [
      {"part": "Introduction", "chapters": [1]},
      {"part": "Part I: Theory", "chapters": [2, 3, 4, 5]},
      {"part": "Part II: Practice", "chapters": [6, 7, 8, 9, 10]}
    ]
  }
}
```

## Troubleshooting

### "Zotero database locked"
**Cause:** Zotero application is running
**Fix:** Close Zotero before starting the service

### "No collections found"
**Cause:** Wrong path or no chapter collections
**Fix:**
```bash
# Check path
ls $ZOTERO_DATA_PATH/zotero.sqlite

# Verify collections match your pattern
sqlite3 $ZOTERO_DATA_PATH/zotero.sqlite "SELECT collectionName FROM collections;"
```

### "Indexing not working"
```bash
# Check container logs
docker compose logs -f

# Restart
docker compose restart

# Force re-index (deletes and rebuilds)
docker compose down
rm -rf data/vectordb/*
docker compose up -d
```

### "MCP not connecting"
**Fix:** Verify `.claude/config.json` syntax:
```bash
cat .claude/config.json | python -m json.tool
```

The MCP server is configured per-project (not globally), so make sure you're running `claude` from the project directory.

### Slow Performance
1. **Model is already optimized:** Using all-MiniLM-L6-v2 (fast, CPU-friendly)
2. **Reduce batch size:** Edit `config/default.json` → `embedding.batch_size: 16`
3. **Check resource usage:** `docker stats book-research-mcp`

## Project Structure

```
book-research-mcp/
├── README.md                 # This file
├── docker-compose.yml        # Container orchestration
├── Dockerfile
├── requirements.txt          # Python dependencies
├── .env                      # Your paths (NOT committed)
├── .env.example              # Template
├── config.local.json         # Your settings (NOT committed)
├── config.schema.json        # Schema documentation
├── .claude/
│   └── config.json           # MCP server config (project-specific)
├── config/
│   └── default.json          # Default settings
├── scripts/
│   └── setup.py              # Interactive setup wizard
├── src/
│   ├── mcp_server.py         # MCP server (main entry point)
│   ├── indexer/
│   │   ├── chunking.py       # Semantic chunking logic
│   │   ├── zotero_indexer.py
│   │   └── scrivener_indexer.py
│   ├── vectordb/
│   │   └── client.py         # Qdrant wrapper
│   └── watcher/
│       └── file_watcher.py   # File monitoring daemon
└── data/                     # Vector DB storage (gitignored)
```

## Performance Tips

1. **Initial indexing is slow** - Large libraries may take 10-30 minutes
2. **Incremental updates are fast** - Only changed files are re-processed
3. **Model optimized for CPU** - all-MiniLM-L6-v2 is fast without GPU
4. **Adjust relevance threshold** - Lower scores (0.6) cast wider net, higher (0.8) more precise
5. **Monitor disk space** - Vector DB uses ~10-20% of source material size

## Contributing

Contributions welcome! Areas we'd love help with:

- Additional document formats (DOCX, Markdown, EPUB)
- Web clipper integration
- Export formats (Obsidian, Notion, Logseq)
- Better chunking strategies
- Multi-language support

See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines.

## Roadmap

- [ ] Obsidian vault integration
- [ ] Web-based dashboard
- [ ] Citation export (BibTeX, CSL)
- [ ] Outline generation
- [ ] Duplicate detection
- [ ] Research gap analysis automation

## License

MIT License - see [LICENSE](./LICENSE)

## Acknowledgments

Built with:
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Qdrant](https://qdrant.tech/) - Vector database
- [sentence-transformers](https://www.sbert.net/) - Embeddings
- [Anthropic Claude](https://www.anthropic.com/claude)
- [watchdog](https://python-watchdogs.readthedocs.io/)
- [pypdf](https://pypdf.readthedocs.io/)

## Support & Community

- 📖 [Documentation](./docs/)
- 💬 [Discussions](https://github.com/yourusername/book-research-mcp/discussions)
- 🐛 [Issue Tracker](https://github.com/yourusername/book-research-mcp/issues)

## FAQ

**Q: Does this draft content for me?**
A: No. It organizes and analyzes your research so you can write better. The actual writing is yours.

**Q: Do I need to keep Zotero running?**
A: No, close it before starting. The indexer needs exclusive database access.

**Q: Will this work without Scrivener?**
A: Currently Scrivener-only, but the architecture is extensible. PRs welcome for Word/Google Docs!

**Q: How much disk space?**
A: ~10-20% of source material size. 10GB library → ~1-2GB for embeddings.

**Q: Can I use this without Docker?**
A: Yes, but Docker is recommended. Manual setup requires Python env, Qdrant installation, etc.

**Q: Is my research sent to the cloud?**
A: Indexing happens 100% locally. Only Claude Code queries (via MCP) use the Claude API.

**Q: Can I index multiple books?**
A: Yes! Run separate containers with different configs, or use project profiles.

---

**Note**: This tool helps you understand your materials, not replace your writing process.
