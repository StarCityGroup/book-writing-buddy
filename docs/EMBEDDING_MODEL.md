# Embedding Model Configuration

## Critical: Vector Dimension Consistency

The embedding model and vector dimensions **must match** across all components, or you'll get runtime errors when indexing or searching.

## Current Configuration

**Default Setup (config/default.json):**
- Model: `all-MiniLM-L6-v2`
- Vector Size: `384` dimensions
- Distance Metric: Cosine similarity

This configuration is optimized for:
- ✅ Fast indexing and search
- ✅ Lower memory usage
- ✅ Good accuracy for book research

## Common Embedding Models

| Model | Dimensions | Speed | Quality | Use Case |
|-------|-----------|-------|---------|----------|
| `all-MiniLM-L6-v2` | 384 | ⚡️ Fast | Good | Default (balanced) |
| `all-mpnet-base-v2` | 768 | Moderate | Better | Higher accuracy |
| `all-MiniLM-L12-v2` | 384 | Fast | Good+ | Alternative to L6 |
| `paraphrase-multilingual` | 768 | Moderate | Good | Multi-language |

## How Consistency is Enforced

The system now automatically validates embedding dimensions at multiple checkpoints:

### 1. Model Verification (at startup)
```python
# VectorDBClient._verify_embedding_dimensions()
# Tests the model with sample text and verifies dimensions match config
```

If mismatch detected:
```
ValueError: Embedding model produces 768 dimensions but
vector_size is configured as 384.
Common models: all-MiniLM-L6-v2=384, all-mpnet-base-v2=768
```

### 2. Collection Verification (at startup)
```python
# VectorDBClient._ensure_collection()
# Checks existing Qdrant collection dimensions match model
```

If mismatch detected:
```
ValueError: Vector dimension mismatch: collection=768, model=384.
Run: docker exec -it qdrant-qdrant-1 \
  curl -X DELETE http://localhost:6333/collections/book_research
```

## Changing the Embedding Model

### Step 1: Update Configuration

Edit `config/default.json`:

```json
{
  "embedding": {
    "model": "all-mpnet-base-v2",  // Changed from all-MiniLM-L6-v2
    "vector_size": 768              // Changed from 384
  }
}
```

### Step 2: Delete Existing Collection

The Qdrant collection must be recreated with new dimensions:

```bash
# Option A: Via Docker
docker exec -it qdrant-qdrant-1 \
  curl -X DELETE http://localhost:6333/collections/book_research

# Option B: Via CLI (if Qdrant is running locally)
curl -X DELETE http://localhost:6333/collections/book_research
```

### Step 3: Re-index

```bash
# Via CLI command
uv run main.py
> /reindex

# Or via indexer script
docker compose run --rm indexer
```

## Troubleshooting

### Error: "Vector dimension mismatch"

**Cause:** Existing Qdrant collection has different dimensions than configured model.

**Solution:**
1. Delete the collection (see Step 2 above)
2. Restart the application (will auto-create collection with correct dimensions)
3. Re-index your data

### Error: "Embedding model produces wrong dimensions"

**Cause:** Model in config doesn't match vector_size in config.

**Solution:** Update both fields in `config/default.json` to match:

```json
// ✅ Correct
{"model": "all-MiniLM-L6-v2", "vector_size": 384}

// ❌ Wrong
{"model": "all-mpnet-base-v2", "vector_size": 384}
```

### Performance Issues After Changing Models

If you switch to a larger model (e.g., 768 dimensions):
- Indexing will be slower
- Search will be slower
- Memory usage will double
- Accuracy may improve slightly

**Recommendation:** Stick with `all-MiniLM-L6-v2` (384) unless you need the extra accuracy.

## Where Dimensions Are Used

1. **VectorDBClient** (`src/vectordb/client.py`)
   - Default parameters now match config
   - Validates on initialization

2. **BookRAG** (`src/rag.py`)
   - Hardcoded to match config defaults
   - Uses VectorDBClient with explicit parameters

3. **Indexers** (`src/indexer/`)
   - All load from `config/default.json`
   - Pass to VectorDBClient explicitly

4. **CLI /reindex** (`src/cli.py`)
   - Loads from config
   - Passes to VectorDBClient

## Environment Variables

You can override the model via environment variables (advanced):

```bash
# .env
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_VECTOR_SIZE=768
```

But this is **not recommended** - use `config/default.json` instead for consistency.

## Verification

To verify your configuration is consistent:

```python
# Start the CLI
uv run main.py

# You should see this log message:
# ✓ Embedding dimensions verified: 384 (model matches config)
```

If you see errors, the system will refuse to start and tell you exactly what's wrong.

## Summary

✅ **Fixed Issues:**
- VectorDBClient defaults now match config (384 dimensions)
- Automatic validation prevents dimension mismatches
- Clear error messages with fix instructions

✅ **Safety Guarantees:**
- Model dimensions verified at startup
- Collection dimensions verified at startup
- System refuses to run with mismatched config

✅ **Developer Experience:**
- All components load from single config file
- Consistent defaults across the codebase
- Helpful error messages guide you to fix issues
