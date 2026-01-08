# Offline Operation Guide

This document explains the offline capabilities of Book Writing Buddy and how to achieve 100% offline operation.

## Quick Summary

**Good News:** The app is ~90% offline-capable already!

- ✅ **Embeddings**: Already offline via `sentence-transformers`
- ✅ **Vector Database**: Qdrant runs locally in Docker
- ✅ **Data Sources**: Zotero + Scrivener are local files
- ⚠️ **LLM Agent**: Currently needs internet (LiteLLM/OpenAI API)

**To go fully offline:** Add Ollama as LLM provider (see below)

## What Works Offline (Already)

## Setup (Already Complete!)

The offline setup has been configured with the following changes:

### 1. Local Model Cache

Models are cached in: `./data/models/`

The embedding model has been pre-downloaded to this directory.

### 2. Docker Configuration

`docker-compose.yml` now mounts the model cache into the container:
- Volume: `./data/models:/models:ro`
- Environment: `MODEL_CACHE_DIR=/models`

### 3. Code Changes

`src/vectordb/client.py` updated to:
- Accept `model_cache_dir` parameter
- Load models from local cache when specified
- Read cache path from `MODEL_CACHE_DIR` environment variable

### 4. Environment Configuration

`.env` includes:
```bash
MODEL_CACHE_DIR=./data/models
```

## Verification

To verify offline operation is working:

```bash
# Inside container with network disabled
docker exec book-research-watcher uv run python -c "
import os
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_OFFLINE']='1'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder='/models')
print('✓ Offline operation working!')
"
```

## Re-downloading the Model

If you need to update or re-download the model:

```bash
# Run the download script
uv run python scripts/download_model.py

# Rebuild containers
docker compose down
docker compose up --build -d
```

## Model Details

- **Model Name**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Size**: ~90 MB
- **Cache Location**: `./data/models/models--sentence-transformers--all-MiniLM-L6-v2/`

## Troubleshooting

### Model not found error
- Ensure `data/models/` directory exists
- Run `uv run python scripts/download_model.py`
- Check volume mounts in `docker-compose.yml`

### Network errors despite offline setup
- Verify `MODEL_CACHE_DIR` is set in both `.env` and container environment
- Check that model files exist in `data/models/`
- Rebuild container: `docker compose up --build -d`

### Permission errors
- Model cache directory is mounted read-only (`:ro`)
- Container shouldn't need write access to models
- If issues persist, remove `:ro` flag from docker-compose.yml

## Benefits

✅ **No internet required** - Works completely offline
✅ **Faster startup** - No download wait time
✅ **Consistent versions** - Model version locked locally
✅ **Privacy** - No external API calls for embeddings
