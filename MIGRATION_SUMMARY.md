# Migration from MCP to Claude Code Skills

## What Changed

Migrated from Model Context Protocol (MCP) server architecture to Claude Code skills for simpler, more direct integration.

## Removed

### Files Deleted
- `.claude/mcp.json` - MCP server configuration
- `src/mcp_server.py` - MCP server implementation
- `scripts/test_mcp_tools.py` - MCP testing script
- `Dockerfile` - Container build file (no longer needed)

### Docker Services Changed
- Renamed `book-research-mcp` → `book-research-indexer`
- Removed MCP server from container
- Container now only runs: indexer + file watcher daemon
- Qdrant container unchanged

## Added

### Claude Code Skills (`.claude/skills/`)

Created 5 focused skills that replace the MCP tools:

1. **search-research** - Semantic search through indexed materials
   - Replaces MCP `search_research` tool
   - Direct Qdrant access with embeddings

2. **get-annotations** - Retrieve Zotero annotations
   - Replaces MCP annotation retrieval
   - Direct SQLite query to Zotero database

3. **analyze-gaps** - Identify research gaps
   - Replaces MCP gap analysis tool
   - Analyzes source density and coverage

4. **find-similar** - Detect similar/duplicate content
   - Replaces MCP similarity detection
   - Configurable similarity threshold

5. **get-chapter-info** - Comprehensive chapter overview
   - New skill (no MCP equivalent)
   - Combines Zotero and Scrivener stats

### Documentation Updates

- `README.md` - Completely rewritten for skills-based approach
- `CLAUDE.md` - Updated with skills usage and removed MCP references
- Skills include `skill.md` documentation files

## Architecture Changes

### Before (MCP)
```
User → Claude Code → MCP Client → Docker Container → MCP Server → Qdrant/Zotero
```

### After (Skills)
```
User → Claude Code → Skills (Python scripts) → Qdrant/Zotero
```

## Benefits of Skills Approach

1. **Simpler** - No Docker container management for the MCP server
2. **Faster** - Direct access to Qdrant and Zotero, no container overhead
3. **Easier debugging** - Plain Python scripts, easier to modify and test
4. **Less configuration** - No MCP protocol complexity
5. **More flexible** - Skills can be run independently

## What Stayed the Same

- Qdrant vector database (still in Docker)
- **Indexing container** (renamed to `book-research-indexer`)
  - File watcher daemon
  - Automatic re-indexing on file changes
  - Initial indexing on startup
- Indexing pipeline (`src/indexer/`)
- Vector database client (`src/vectordb/client.py`)
- Chunking and embedding logic
- Core skill implementations (`src/skills/`)
- Configuration files (`config/`)

## Migration Steps for Users

If you had the old MCP version running:

1. Stop and remove old containers:
   ```bash
   docker compose down
   docker rm book-research-mcp  # If not removed
   ```

2. Pull latest code (this version)

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Ensure `.env` file exists with paths:
   ```bash
   cp .env.example .env
   # Edit .env with your actual paths
   ```

5. Rebuild and start containers:
   ```bash
   docker compose up --build -d
   ```

6. Watch indexer logs:
   ```bash
   docker compose logs -f indexer
   ```

7. Use Claude Code with skills:
   ```bash
   claude
   ```

## Testing Skills

Skills are automatically available in Claude Code. Test with:

```
"Search for firewall implementations in chapter 2"
"Get annotations for chapter 9"
"Analyze research gaps"
```

Or test manually:
```bash
# Search skill
echo '{"query": "test", "limit": 5}' | uv run .claude/skills/search-research/main.py

# Annotations skill
echo '{"chapter_number": 1}' | uv run .claude/skills/get-annotations/main.py
```

## Troubleshooting

### Skills not found
- Make sure you're in the project directory
- Check `.claude/skills/` exists with skill folders

### Import errors
- Run `uv sync` to install dependencies
- Verify `QDRANT_URL` environment variable is set

### Empty results
- Ensure Qdrant is running: `docker ps`
- Check data is indexed: skills will return empty arrays if no data

## Next Steps

1. Verify Docker Compose starts cleanly: `docker compose up -d`
2. Check Qdrant is accessible: `curl http://localhost:6333/collections`
3. Index your data (if not already): `uv run python scripts/index_all.py`
4. Test skills in Claude Code

## Rollback (if needed)

The MCP approach is still in git history. To rollback:
```bash
git log --oneline | grep -i mcp  # Find commit before migration
git checkout <commit-hash>
```
