# Sync Checker and Search Tool Fixes

## Date: 2024-12-24

## Critical Bugs Found and Fixed

### Bug #1: Sync Checker Called Non-Existent Method

**Problem:**
- `src/sync_checker.py` line 92 and 121 called `self.qdrant.query_by_metadata()`
- This method **did not exist** in `VectorDBClient`
- Exception was silently caught (lines 110, 139: `except Exception: return {}`)
- Result: sync checker always returned empty dicts, making ALL chapters appear missing

**Impact:**
- Sync check reported false negatives (e.g., Chapter 1 reported as missing despite having 3 Zotero items)
- User couldn't trust sync status reports
- Agent would give incorrect recommendations

**Fix:**
- Added `query_by_metadata()` method to `src/vectordb/client.py` (lines 277-341)
- Uses Qdrant's efficient `scroll` API to retrieve all matching points
- Supports unlimited results (no artificial limits)
- Returns formatted dicts with id, metadata, and text

### Bug #2: Hard-Coded 1000 Chunk Limit

**Problem:**
- Sync checker had `limit=1000` hard-coded in lines 93 and 122
- Database has 6,378 total chunks (5,587 Zotero + 790 Scrivener)
- Only first 1,000 chunks were being checked
- Chapters appearing after position 1000 in query results were completely invisible to sync checker

**Impact:**
- Chapters with fewer chunks or appearing later in alphabetical order were missed
- Sync check was incomplete and unreliable

**Fix:**
- Changed `limit=1000` to `limit=None` in both places
- Now retrieves ALL chunks using scroll pagination
- Batch size of 100 for efficient memory usage

### Bug #3: Mixed Zotero and Scrivener Search Results

**Problem:**
- `search_research` tool (src/tools.py line 32) searched BOTH Zotero and Scrivener together
- No way to filter by `source_type`
- Agent couldn't distinguish published research from draft notes
- Research questions mixed in author's personal notes with published papers

**Impact:**
- When user asked "what research exists on X", results included their own draft notes
- When user asked "what did I write about X", results included research papers
- No way to intentionally search just one source type

**Fix:**
- Added `source_type` parameter to `search_research()` tool
  - `source_type="zotero"` → Search ONLY research papers/articles/books
  - `source_type="scrivener"` → Search ONLY manuscript drafts/notes
  - `source_type=None` → Search BOTH (default behavior)
- Updated system prompt in `agent_v2.py` with guidance on when to use each filter
- Added `source_type` field to search results so agent knows what each result is

## How Data is Stored

Both Zotero and Scrivener data are stored in a **single Qdrant collection** called `book_research` with:
- **6,378 total points** (chunks)
- **5,587 Zotero chunks** (`source_type: "zotero"`)
- **790 Scrivener chunks** (`source_type: "scrivener"`)

### Zotero Metadata Fields
```json
{
  "source_type": "zotero",
  "item_id": 22314,
  "item_key": "3RV7HWRY",
  "title": "Rethinking Government for the Era of Agentic AI",
  "collection_name": "25. financing the firewall",
  "chapter_number": 25,
  "file_path": "/mnt/zotero/storage/CAFPFA6M/...",
  "file_type": "pdf",
  "total_pages": 104,
  "page_number": 95
}
```

### Scrivener Metadata Fields
```json
{
  "source_type": "scrivener",
  "file_path": "/mnt/scrivener/Files/Data/...",
  "doc_type": "draft",  // or "notes"
  "scrivener_id": "29E3281A-5F22-4CEA-B38C-C011C24A8DFD",
  "chapter_number": 24,
  "chapter_title": "Intelligence for Adaptation",
  "parent_title": "Intelligence for Adaptation"
}
```

## Testing Recommendations

### 1. Test Sync Check
```bash
uv run main.py
# Then type: "Check sync status"
```

Expected: Should now see ALL chapters correctly identified, not false negatives.

### 2. Test Source Type Filtering
```bash
uv run main.py
# Then try these queries:
# "Search for remote sensing in Zotero research only"
# "What did I write about remote sensing in my manuscript?"
# "Find remote sensing in both research and my drafts"
```

Expected:
- First query should return ONLY Zotero research papers
- Second query should return ONLY Scrivener draft content
- Third query should return both

### 3. Verify Data Counts
```bash
curl -s http://localhost:6333/collections/book_research | python3 -m json.tool
```

Expected: `"points_count": 6378`

## Files Modified

1. **src/vectordb/client.py**
   - Added `query_by_metadata()` method using scroll API

2. **src/sync_checker.py**
   - Removed `limit=1000` restrictions
   - Now retrieves ALL chunks with `limit=None`

3. **src/tools.py**
   - Added `source_type` parameter to `search_research()` tool
   - Updated return dict to include `source_type_filter`

4. **src/agent_v2.py**
   - Updated system prompt to explain source_type filtering
   - Added guidance on when to use zotero/scrivener/both

## Can the Agent Distinguish Between Source Types?

**YES!** The agent can distinguish in multiple ways:

### 1. Proactive Filtering (BEFORE search)
Agent can choose to search:
- ONLY Zotero research: `source_type="zotero"`
- ONLY Scrivener drafts: `source_type="scrivener"`
- Both sources: `source_type=None`

### 2. Result Inspection (AFTER search)
Every search result includes `source_type` metadata:
```python
{
    "text": "heat mapping requires hyperlocal resolution",
    "score": "88%",
    "source": "Urban Heat Islands Study",
    "chapter": 13,
    "source_type": "zotero"  # ← Agent sees this!
}
```

### 3. Citation Guidance
System prompt instructs agent to cite differently:
- **Zotero**: "According to [Source Title] (Zotero research)..."
- **Scrivener**: "From your manuscript draft (Chapter X)..."

This ensures user always knows if findings come from published research or their own work.

## Impact on User Experience

**Before:**
- Sync check reported false negatives
- Search mixed research papers with draft notes
- No way to search just one source type
- Agent couldn't reliably answer "what research exists on X"
- Agent couldn't distinguish citations from author's own notes

**After:**
- Sync check accurately reports all chapters
- Agent can search Zotero research separately from Scrivener drafts
- Agent sees source_type in every result and cites accordingly
- Clear distinction between published sources and author's own work
- More accurate answers to research questions

## Next Steps

1. Test sync check with user's actual data
2. Test source_type filtering with real queries
3. Update README.md to document source_type parameter
4. Consider adding source_type filter to other analysis tools
