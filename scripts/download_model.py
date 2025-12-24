#!/usr/bin/env python3
"""
Download and cache the sentence-transformers embedding model locally.

This ensures the model is available for offline use in Docker containers.
"""

from pathlib import Path

from sentence_transformers import SentenceTransformer

# Model configuration (must match config/default.json)
MODEL_NAME = "all-MiniLM-L6-v2"
CACHE_DIR = Path(__file__).parent.parent / "data" / "models"


def download_model():
    """Download and cache the embedding model."""
    print(f"Downloading model: {MODEL_NAME}")
    print(f"Cache directory: {CACHE_DIR}")

    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Download model (will cache to CACHE_DIR)
    model = SentenceTransformer(MODEL_NAME, cache_folder=str(CACHE_DIR))

    # Test the model
    test_embedding = model.encode(["test sentence"])
    print("✓ Model downloaded successfully!")
    print(f"✓ Embedding dimension: {test_embedding.shape[1]}")
    print(f"✓ Cached at: {CACHE_DIR}")


if __name__ == "__main__":
    download_model()
