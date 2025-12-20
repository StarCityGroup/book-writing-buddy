# BookRAG API Documentation

Complete API reference for the BookRAG research analysis system.

## Table of Contents

- [Core Methods](#core-methods)
- [Cross-Chapter Analysis](#cross-chapter-analysis)
- [Source Diversity & Quality](#source-diversity--quality)
- [Export & Summarization](#export--summarization)
- [Research Timeline](#research-timeline)
- [Smart Recommendations](#smart-recommendations)
- [Agent Integration](#agent-integration)

---

## Core Methods

### `search(query, filters=None, limit=20, score_threshold=0.7)`

Semantic search through indexed research materials.

**Parameters:**
- `query` (str): Search query text
- `filters` (dict, optional): Filter criteria
  - `chapter_number` (int): Filter by chapter
  - `source_type` (str): "zotero" or "scrivener"
- `limit` (int): Maximum results (default: 20)
- `score_threshold` (float): Minimum similarity (0-1, default: 0.7)

**Returns:**
List of dicts with `text`, `score`, and `metadata` fields

**Example:**
```python
rag = BookRAG()
results = rag.search(
    query="infrastructure failures",
    filters={"chapter_number": 9, "source_type": "zotero"},
    limit=10
)
```

### `get_chapter_info(chapter_number)`

Get comprehensive chapter information.

**Parameters:**
- `chapter_number` (int): Chapter number

**Returns:**
Dict with:
- `indexed_chunks` (int): Total indexed chunks
- `zotero` (dict): Source count, chunk count, source list
- `scrivener` (dict): Chunk count, estimated word count

**Example:**
```python
info = rag.get_chapter_info(5)
print(f"Chapter 5 has {info['zotero']['source_count']} sources")
```

---

## Cross-Chapter Analysis

### `find_cross_chapter_themes(keyword, min_chapters=2)`

Track a theme or concept across multiple chapters.

**Parameters:**
- `keyword` (str): Theme/concept to track
- `min_chapters` (int): Minimum chapters to appear in (default: 2)

**Returns:**
Dict with:
- `keyword` (str): Search term used
- `total_chapters` (int): Chapters containing theme
- `total_mentions` (int): Total mentions across all chapters
- `meets_threshold` (bool): Whether min_chapters threshold is met
- `chapters` (list): Chapter-by-chapter breakdown with mentions

**Example:**
```python
results = rag.find_cross_chapter_themes("adaptation trap")
for ch in results['chapters']:
    print(f"Chapter {ch['chapter_number']}: {len(ch['mentions'])} mentions")
```

**Agent Usage:**
- "Track the theme 'resilience' across chapters"
- "Where does 'infrastructure failure' appear in the book?"
- "Find 'adaptation trap' across all chapters"

### `compare_chapters(chapter1, chapter2)`

Compare research density and coverage between two chapters.

**Parameters:**
- `chapter1` (int): First chapter number
- `chapter2` (int): Second chapter number

**Returns:**
Dict with:
- `chapter1` / `chapter2` (dict): Metrics for each chapter
  - `total_chunks` (int): All indexed chunks
  - `zotero_sources` (int): Number of sources
  - `zotero_chunks` (int): Zotero chunks
  - `scrivener_words` (int): Estimated word count
  - `research_density` (float): Zotero chunks per word
- `comparison` (dict): Comparative analysis
  - `more_sources` (int): Chapter with more sources
  - `more_research_dense` (int): Chapter with higher density
  - `density_ratio` (float): Density ratio between chapters

**Example:**
```python
comp = rag.compare_chapters(3, 7)
if comp['comparison']['more_research_dense'] == 3:
    print("Chapter 3 has more research per word than Chapter 7")
```

**Agent Usage:**
- "Compare chapter 3 and chapter 7"
- "Which has more research, chapter 5 or chapter 12?"
- "Compare research density between chapters 2 and 8"

---

## Source Diversity & Quality

### `analyze_source_diversity(chapter)`

Analyze diversity of source types for a chapter using Simpson's Diversity Index.

**Parameters:**
- `chapter` (int): Chapter number

**Returns:**
Dict with:
- `total_sources` (int): Unique source count
- `source_types` (dict): Count by type (book, article, webpage, etc.)
- `diversity_score` (float): 0-1 score (0=homogeneous, 1=diverse)
- `most_cited` (list): Top 5 most-referenced sources
- `least_cited` (list): Bottom 5 sources

**Example:**
```python
diversity = rag.analyze_source_diversity(9)
if diversity['diversity_score'] < 0.5:
    print("Chapter 9 relies heavily on few source types")
```

**Agent Usage:**
- "Analyze source diversity for chapter 9"
- "What types of sources does chapter 5 use?"
- "Is chapter 12 relying too heavily on one source type?"

### `identify_key_sources(chapter, min_mentions=3)`

Find most-referenced sources in a chapter.

**Parameters:**
- `chapter` (int): Chapter number
- `min_mentions` (int): Minimum chunks to be "key" (default: 3)

**Returns:**
Dict with:
- `total_sources` (int): All sources in chapter
- `key_sources_count` (int): Sources meeting threshold
- `threshold` (int): Minimum mentions used
- `key_sources` (list): Key sources sorted by mention count
  - Each has: `title`, `source_type`, `chunk_count`, `item_type`

**Example:**
```python
key = rag.identify_key_sources(5, min_mentions=5)
for src in key['key_sources']:
    print(f"{src['title']}: {src['chunk_count']} mentions")
```

**Agent Usage:**
- "What are the key sources for chapter 9?"
- "Which sources am I citing most in chapter 3?"
- "Show me the most referenced sources in chapter 15"

---

## Export & Summarization

### `export_chapter_summary(chapter, format='markdown')`

Export formatted research summary for a chapter.

**Parameters:**
- `chapter` (int): Chapter number
- `format` (str): Output format ('markdown', 'text', or 'json')

**Returns:**
Formatted string containing:
- Overview (indexed chunks, sources, draft status)
- Source diversity metrics
- Key sources list
- Most cited sources
- Generation timestamp

**Example:**
```python
summary = rag.export_chapter_summary(5, format='markdown')
Path('output/chapter5-summary.md').write_text(summary)
```

**Agent Usage:**
- "Export a summary for chapter 9"
- "Give me a research brief for chapter 5"
- "Summarize chapter 12 research"

### `generate_bibliography(chapter=None, style='apa')`

Generate formatted bibliography from Zotero sources.

**Parameters:**
- `chapter` (int, optional): Chapter number (None for all chapters)
- `style` (str): Citation style ('apa', 'mla', 'chicago', or 'raw')

**Returns:**
List of dicts, each containing:
- `citation` (str): Formatted citation
- `title` (str): Source title
- `type` (str): Item type
- `chapters` (list): Chapters using this source
- `raw` (dict): Raw metadata

**Example:**
```python
bib = rag.generate_bibliography(chapter=5, style='apa')
for entry in bib:
    print(entry['citation'])
```

**Agent Usage:**
- "Generate bibliography for chapter 9 in APA format"
- "Show me citations for chapter 5 in MLA style"
- "Create a reference list for the whole book"

---

## Research Timeline

### `get_recent_additions(days=7)`

Get recently indexed research materials.

**Parameters:**
- `days` (int): Days to look back (default: 7)

**Returns:**
Dict with:
- `cutoff_date` (str): ISO format cutoff date
- `sources` (dict): Recently indexed sources by type
  - Each has: `indexed_at`, `age_hours`, `is_recent`

**Example:**
```python
recent = rag.get_recent_additions(days=14)
for source_type, info in recent['sources'].items():
    print(f"{source_type} indexed {info['age_hours']} hours ago")
```

**Agent Usage:**
- "What research have I added recently?"
- "Show me materials added in the last week"
- "What did I index last month?"

### `get_research_timeline(chapter=None)`

Get timeline of research collection by month.

**Parameters:**
- `chapter` (int, optional): Filter by chapter (None for all)

**Returns:**
Dict with:
- `chapter` (int or None): Filtered chapter
- `total_periods` (int): Number of time periods
- `timeline` (list): Monthly breakdown
  - Each has: `month`, `count`, `chapters`, `sources` (sample)

**Example:**
```python
timeline = rag.get_research_timeline()
for period in timeline['timeline']:
    print(f"{period['month']}: {period['count']} chunks")
```

**Agent Usage:**
- "Show my research timeline"
- "When did I collect research for chapter 9?"
- "Timeline of research for the whole book"

---

## Smart Recommendations

### `suggest_related_research(chapter, limit=5)`

Suggest research from other chapters that might be relevant.

**Parameters:**
- `chapter` (int): Chapter to find suggestions for
- `limit` (int): Maximum suggestions (default: 5)

**Returns:**
Dict with:
- `chapter` (int): Target chapter
- `suggestions_count` (int): Total suggestions found
- `chapters_with_suggestions` (int): Chapters with relevant research
- `suggestions` (list): Grouped by source chapter
  - Each has: `chapter`, `chapter_title`, `items` (relevant chunks)

**Example:**
```python
suggestions = rag.suggest_related_research(5)
for ch_group in suggestions['suggestions']:
    print(f"Chapter {ch_group['chapter']}: {len(ch_group['items'])} relevant items")
```

**Agent Usage:**
- "Suggest related research for chapter 9"
- "What research from other chapters is relevant to chapter 5?"
- "Find cross-references for chapter 12"

---

## Agent Integration

All methods are automatically accessible through natural language queries in the TUI agent.

### Example Queries

**Cross-Chapter Analysis:**
- "Track 'climate adaptation' across all chapters"
- "Compare research density between chapters 5 and 9"

**Source Quality:**
- "Analyze source diversity for chapter 3"
- "Show me the most cited sources in chapter 12"

**Export:**
- "Export a summary for chapter 7"
- "Generate APA bibliography for chapter 4"

**Timeline:**
- "What research have I added recently?"
- "Show research timeline for chapter 9"

**Recommendations:**
- "Suggest related research for chapter 5"
- "What from other chapters is relevant to chapter 8?"

### Query Classification

The agent automatically classifies queries and routes to the appropriate tool:

| Query Pattern | Routes To |
|--------------|-----------|
| "track theme", "across chapters" | `cross_chapter_theme` |
| "compare chapter", "versus" | `compare_chapters` |
| "source diversity", "balance of sources" | `source_diversity` |
| "key sources", "most cited" | `key_sources` |
| "export summary", "research brief" | `export_summary` |
| "bibliography", "citations" | `bibliography` |
| "recent", "timeline" | `timeline` |
| "related research", "suggest" | `related_research` |

---

## Return Value Reference

### Common Metadata Fields

All search results include metadata with these possible fields:

- `chapter_number` (int): Chapter number
- `chapter_title` (str): Chapter title
- `title` (str): Source document title
- `source_type` (str): "zotero" or "scrivener"
- `item_type` (str): Zotero item type (book, article, etc.)
- `authors` (str): Author names
- `year` (str): Publication year
- `publisher` (str): Publisher name
- `url` (str): Web URL
- `doi` (str): DOI identifier
- `page` (int): Page number
- `date_added` (str): ISO timestamp

### Score Interpretation

Similarity scores (0-1):
- **0.9-1.0**: Extremely similar/relevant
- **0.8-0.9**: Highly relevant
- **0.7-0.8**: Moderately relevant
- **0.6-0.7**: Somewhat relevant
- **<0.6**: Low relevance

### Diversity Score Interpretation

Simpson's Diversity Index (0-1):
- **0.0-0.3**: Low diversity (homogeneous sources)
- **0.3-0.6**: Moderate diversity
- **0.6-0.8**: High diversity
- **0.8-1.0**: Very high diversity (balanced mix)

---

## Error Handling

All methods return error dicts instead of raising exceptions:

```python
result = rag.get_chapter_info(999)
if result.get("error"):
    print(f"Error: {result['error']}")
```

Common error messages:
- `"No chapter number specified"`: Chapter parameter missing
- `"Need two chapter numbers to compare"`: Comparison needs 2 chapters
- `"No theme keyword specified"`: Theme search missing keyword
- `"Zotero database not found"`: Database path incorrect

---

## Performance Notes

- **Search operations**: Sub-second for most queries
- **Timeline queries**: May be slow for large datasets (use chapter filter)
- **Bibliography generation**: O(n) where n = number of sources
- **Cross-chapter analysis**: Limited to 100 results by default

## Best Practices

1. **Use filters**: Always filter by chapter when possible for faster queries
2. **Adjust thresholds**: Lower `score_threshold` if getting no results
3. **Batch operations**: Use chapter filters rather than querying all chapters
4. **Cache results**: Results don't change unless index is updated
5. **Monitor diversity**: Check diversity scores during research to ensure balanced sources
