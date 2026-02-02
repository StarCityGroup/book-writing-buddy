# Reindexing System

## Overview

The reindexing system allows selective reindexing of Zotero and Scrivener data sources independently. This is useful when you've updated one source but not the other, avoiding the need to reindex everything.

## Implementation

### CLI Tool: `scripts/reindex.py`

The main reindex script provides a CLI interface for selective reindexing:

```bash
uv run scripts/reindex.py [options]
```

**Options:**
- `--source {zotero|scrivener|both}` - Select which source(s) to reindex (default: both)
- `--force` - Delete existing data before reindexing (requires confirmation)

### Architecture

The reindex system leverages existing indexer classes:

1. **ZoteroIndexer** (`src/indexer/zotero_indexer.py`)
   - Indexes Zotero collections into vector database
   - Returns stats: `collections_indexed`, `documents_indexed`, `chunks_indexed`

2. **ScrivenerIndexer** (`src/indexer/scrivener_indexer.py`)
   - Indexes Scrivener RTF documents into vector database
   - Returns stats: `documents_indexed`, `chunks_indexed`

3. **VectorDBClient** (`src/vectordb/client.py`)
   - Provides `delete_by_source(source_type)` for selective deletion
   - Tags all points with `source_type` metadata ("zotero" or "scrivener")

### Data Isolation

Each source is isolated using metadata filters:

- **Zotero points**: `source_type: "zotero"`
- **Scrivener points**: `source_type: "scrivener"`

This allows deletion of one source without affecting the other:

```python
vectordb.delete_by_source("zotero")    # Only deletes Zotero data
vectordb.delete_by_source("scrivener") # Only deletes Scrivener data
```

## Use Cases

### 1. Reindex Zotero Only

When you've added new research materials or reorganized collections:

```bash
uv run scripts/reindex.py --source zotero
```

- Keeps Scrivener manuscript data intact
- Re-indexes all Zotero collections
- Useful after bulk imports or collection restructuring

### 2. Reindex Scrivener Only

When you've edited drafts or reorganized chapters:

```bash
uv run scripts/reindex.py --source scrivener
```

- Keeps Zotero research data intact
- Re-indexes all Scrivener documents
- Useful after major manuscript revisions

### 3. Reindex Both

When you've changed both sources or need a complete refresh:

```bash
uv run scripts/reindex.py --source both
```

- Re-indexes everything
- Equivalent to full reindex but more controlled

### 4. Force Reindex

When you want to ensure clean slate (deletes before reindexing):

```bash
uv run scripts/reindex.py --source zotero --force
```

- Prompts for confirmation
- Deletes existing data before reindexing
- Prevents duplicate entries from overlapping indexes

## Comparison with Full Database Reset

### Selective Reindex (scripts/reindex.py)

**Pros:**
- Fast - only reindexes selected source
- Preserves other sources
- No need to stop Docker containers
- Controlled and reversible

**Cons:**
- Doesn't fix underlying database corruption
- Requires source isolation to work correctly

### Full Database Reset

**Pros:**
- Guaranteed clean slate
- Fixes database corruption issues
- Simple and foolproof

**Cons:**
- Slow - reindexes everything
- Requires stopping Docker containers
- Loses all data temporarily

**Full reset procedure:**
```bash
docker compose down
rm -rf data/qdrant_storage/*
docker compose up --build -d
```

## Implementation Details

### Reindex Flow

1. **Load Configuration**
   - Read `config/default.json`
   - Get environment variables (ZOTERO_PATH, SCRIVENER_PROJECT_PATH)

2. **Connect to Qdrant**
   - Initialize VectorDBClient
   - Verify collection exists

3. **Optional Delete**
   - If `--force` flag set, prompt for confirmation
   - Call `vectordb.delete_by_source(source_type)`

4. **Reindex Source(s)**
   - Instantiate appropriate indexer(s)
   - Call `index_all()` method
   - Collect statistics

5. **Report Results**
   - Show per-source statistics
   - Display total collection size

### Error Handling

The script handles common errors gracefully:

- **Missing environment variables**: Logs error and skips that source
- **Qdrant connection failure**: Exits with clear error message
- **Indexing errors**: Logs error but continues with other sources
- **User cancellation**: Exits cleanly when force confirmation declined

## Future Enhancements

Potential improvements:

1. **Incremental Sync**: Detect changes and only reindex modified files
   - Currently implemented for Scrivener (`ScrivenerSyncDetector`)
   - Could be added to Zotero indexer

2. **Partial Reindex**: Reindex specific chapters or collections
   - `--chapter 5` - Reindex only chapter 5
   - `--collection "Chapter 9"` - Reindex only one Zotero collection

3. **Dry Run Mode**: Show what would be reindexed without doing it
   - `--dry-run` flag to preview changes

4. **Progress Bars**: Visual feedback during long operations
   - Use `tqdm` for progress indication

5. **Validation**: Check data integrity after reindexing
   - Verify expected number of documents indexed
   - Check for missing chapters

## Related Files

- `scripts/reindex.py` - Main CLI script
- `src/indexer/zotero_indexer.py` - Zotero indexing logic
- `src/indexer/scrivener_indexer.py` - Scrivener indexing logic
- `src/indexer/run_initial_index.py` - Initial indexing (used by Docker)
- `src/vectordb/client.py` - Vector database client with deletion methods

## Testing

To test the reindex system:

```bash
# 1. Check current state
curl http://localhost:6333/collections/book_research | jq '.result.points_count'

# 2. Run reindex
uv run scripts/reindex.py --source zotero

# 3. Verify new state
curl http://localhost:6333/collections/book_research | jq '.result.points_count'

# 4. Query to ensure data is accessible
uv run main.py
# Ask: "Search for climate change in chapter 5"
```

## Troubleshooting

### "Source type not found"
**Issue**: No data for specified source exists
**Solution**: This is normal for initial reindex; just indexes new data

### "Collection not found"
**Issue**: Qdrant collection doesn't exist
**Solution**: Run initial index first: `docker compose up --build -d`

### "Zotero database locked"
**Issue**: Zotero application is running
**Solution**: Close Zotero before reindexing

### "Permission denied"
**Issue**: Script not executable
**Solution**: `chmod +x scripts/reindex.py`

### "No statistics returned"
**Issue**: Indexing failed silently
**Solution**: Check logs for detailed error messages
