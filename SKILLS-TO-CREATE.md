# Skills to Create for Book Research MCP

## Current State Analysis

**What exists:**
- MCP server with only 1 tool implemented: `get_indexing_status()`
- Vector database with Qdrant storing 384-dim embeddings
- Indexers for Zotero (PDF, HTML, text) and Scrivener (RTF)
- Semantic chunking (~500 chars with 100 char overlap)
- File watcher for automatic re-indexing
- Daemon mode for background indexing

**What's missing:**
- The 4 main MCP tools mentioned in README are not implemented:
  - `prepare_chapter(num)`
  - `search_research(query, filters)`
  - `analyze_theme_across_manuscript(theme)`
  - `find_cross_chapter_connections(num)`

---

## Recommended Skills to Add

### 1. **Citation Extraction & Management Skill**
**Purpose:** Extract and format citations from Zotero items for use in manuscript

**Capabilities:**
- Extract bibliographic metadata from Zotero database
- Format citations in multiple styles (Chicago, APA, MLA)
- Generate bibliography for specific chapters
- Track which sources have been cited vs. uncited
- Export to BibTeX/CSL for reference managers

**Value:** Currently, the system indexes PDFs but doesn't preserve Zotero's rich metadata (authors, publication dates, journals, etc.). This skill would make citation management seamless.

**Files to modify:**
- `src/indexer/zotero_indexer.py` - enhance to extract full item metadata
- Create new: `src/skills/citation_manager.py`
- Add MCP tool: `get_citations_for_chapter(chapter_num, style='chicago')`

---

### 2. **Outline Generation & Structure Analysis Skill**
**Purpose:** Analyze manuscript structure and generate chapter outlines

**Capabilities:**
- Parse Scrivener's .scrivx file to understand document hierarchy
- Generate outlines showing chapter structure and subsections
- Identify structural gaps (missing sections, uneven lengths)
- Compare current structure against planned chapter organization
- Suggest reorganization based on thematic clustering

**Value:** Currently ignores Scrivener's organizational structure. This skill would provide structural insights.

**Files to modify:**
- `src/indexer/scrivener_indexer.py` - add .scrivx parsing
- Create new: `src/skills/outline_analyzer.py`
- Add MCP tools:
  - `get_chapter_outline(chapter_num)`
  - `analyze_manuscript_structure()`

---

### 3. **Smart Quote & Fact Extraction Skill**
**Purpose:** Identify and extract notable quotes, statistics, and facts from sources

**Capabilities:**
- Use NLP to identify key sentences (quotes, statistics, definitions)
- Extract numerical data with context
- Identify expert quotes with proper attribution
- Tag facts by type (statistic, case study, definition, quote)
- Create a "fact bank" searchable by chapter or theme

**Value:** Makes it easy to find compelling evidence without re-reading sources.

**Files to modify:**
- Create new: `src/skills/fact_extractor.py`
- Integrate with: `src/indexer/chunking.py` (run during indexing)
- Add MCP tool: `find_compelling_facts(topic, fact_type=None)`

---

### 4. **Research Gap Detector Skill**
**Purpose:** Identify areas needing more research

**Capabilities:**
- Compare source density across chapters
- Identify topics mentioned but lacking citations
- Detect chapters with fewer sources than average
- Suggest related search terms based on gaps
- Compare manuscript themes against available research

**Value:** Proactively identifies weak areas in research coverage.

**Files to modify:**
- Create new: `src/skills/gap_analyzer.py`
- Add MCP tool: `identify_research_gaps(chapter_num=None)`

---

### 5. **Timeline & Chronology Skill**
**Purpose:** Extract and organize temporal information from sources

**Capabilities:**
- Extract dates and events from documents
- Build chronological timelines of events
- Identify date ranges covered by each chapter
- Detect chronological inconsistencies in draft
- Create event timelines across the manuscript

**Value:** Especially useful for historical or narrative non-fiction.

**Files to modify:**
- Create new: `src/skills/timeline_builder.py`
- Add MCP tools:
  - `build_timeline(start_date, end_date, chapters=None)`
  - `extract_dates_from_chapter(chapter_num)`

---

### 6. **Similarity & Duplication Detector Skill**
**Purpose:** Find duplicate or highly similar content

**Capabilities:**
- Detect near-duplicate chunks in vector database
- Identify sections covering the same topic
- Find redundant sources (same information from multiple PDFs)
- Suggest content consolidation opportunities
- Detect accidental plagiarism from sources

**Value:** Helps avoid repetition and identify redundant research.

**Files to modify:**
- Create new: `src/skills/similarity_detector.py`
- Add MCP tools:
  - `find_similar_content(text, threshold=0.85)`
  - `detect_duplicates_in_chapter(chapter_num)`

---

### 7. **Annotation & Note Aggregator Skill**
**Purpose:** Collect and organize Zotero annotations and notes

**Capabilities:**
- Extract highlights and annotations from Zotero database
- Parse PDF annotations if embedded in files
- Organize notes by chapter/tag
- Create "research notes" digest for each chapter
- Link annotations back to source documents

**Value:** Zotero annotations are separate from PDF text; this surfaces your own thoughts.

**Files to modify:**
- `src/indexer/zotero_indexer.py` - query annotations table
- Create new: `src/skills/annotation_aggregator.py`
- Add MCP tool: `get_annotations(chapter_num=None, source_id=None)`

---

## Priority Recommendations (Based on User Feedback)

**User priorities: (3) Core tools, (2) Quote/Fact extraction, (1) Citations, then (4) Structure**

**Phase 1 (CRITICAL - Complete core functionality):**
1. **Implement 4 missing core MCP tools** - Foundation must work first
2. **Smart Quote & Fact Extraction** - High ROI, mixed content type benefits
3. **Citation Extraction & Management** - Essential for manuscript references

**Phase 2 (Later):**
4. **Outline Generation & Structure Analysis** - Nice to have, can wait
5. **Research Gap Detector** - Analytical insight
6. **Timeline & Chronology** - Useful for historical sections (mixed content)
7. **Annotation & Note Aggregator** - Leverages Zotero notes
8. **Similarity & Duplication Detector** - Quality control

---

## Detailed Implementation Plan

### Phase 1.1: Implement Core MCP Tools (FIRST PRIORITY)

**Files to modify:**
- `src/mcp_server.py` - add 4 new tools to _register_handlers()

**Tool 1: `search_research(query, filters)`**
```python
# Add to list_tools():
{
    "name": "search_research",
    "description": "Semantic search across indexed research materials",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "chapter_number": {"type": "integer", "description": "Optional: filter by chapter"},
            "source_type": {"type": "string", "enum": ["zotero", "scrivener"], "description": "Optional: filter by source"},
            "limit": {"type": "integer", "default": 20, "description": "Max results"}
        },
        "required": ["query"]
    }
}

# Implementation:
async def _search_research(query, chapter_number=None, source_type=None, limit=20):
    filters = {}
    if chapter_number:
        filters['chapter_number'] = chapter_number
    if source_type:
        filters['source_type'] = source_type

    results = self.vectordb.search(query, filters=filters, limit=limit)
    return {
        'query': query,
        'results': results,
        'count': len(results)
    }
```

**Tool 2: `prepare_chapter(chapter_num)`**
```python
# Combines search + metadata extraction for a chapter
async def _prepare_chapter(chapter_num):
    # Get all materials for this chapter
    filters = {'chapter_number': chapter_num}

    # Get Zotero materials
    zotero_results = self.vectordb.search("", filters={**filters, 'source_type': 'zotero'}, limit=100)

    # Get Scrivener draft
    scrivener_results = self.vectordb.search("", filters={**filters, 'source_type': 'scrivener'}, limit=50)

    # Get collection info from Zotero
    collections = self.zotero_indexer.get_collections()
    chapter_collection = next((c for c in collections if c['chapter_number'] == chapter_num), None)

    return {
        'chapter_number': chapter_num,
        'collection_name': chapter_collection['name'] if chapter_collection else None,
        'zotero_sources': len(zotero_results),
        'scrivener_sections': len(scrivener_results),
        'materials': {
            'zotero': zotero_results[:20],  # Top 20 chunks
            'scrivener': scrivener_results[:10]  # Top 10 sections
        }
    }
```

**Tool 3: `analyze_theme_across_manuscript(theme)`**
```python
# Search for theme across all chapters, group by chapter
async def _analyze_theme(theme):
    # Search without filters to get all chapters
    all_results = self.vectordb.search(theme, limit=100)

    # Group by chapter
    by_chapter = {}
    for result in all_results:
        ch_num = result['metadata'].get('chapter_number')
        if ch_num:
            if ch_num not in by_chapter:
                by_chapter[ch_num] = []
            by_chapter[ch_num].append(result)

    # Sort by chapter
    sorted_chapters = sorted(by_chapter.items())

    return {
        'theme': theme,
        'chapters_found': len(by_chapter),
        'total_mentions': len(all_results),
        'by_chapter': [
            {
                'chapter': ch_num,
                'occurrences': len(chunks),
                'top_excerpts': [c['text'][:200] for c in chunks[:3]]
            }
            for ch_num, chunks in sorted_chapters
        ]
    }
```

**Tool 4: `find_cross_chapter_connections(chapter_num)`**
```python
# Find chapters with similar content to specified chapter
async def _find_connections(chapter_num):
    # Get representative chunks from target chapter
    chapter_chunks = self.vectordb.search(
        "",  # Empty query
        filters={'chapter_number': chapter_num},
        limit=10
    )

    if not chapter_chunks:
        return {'error': f'No content found for chapter {chapter_num}'}

    # For each chunk, find similar chunks in OTHER chapters
    connections = {}
    for chunk in chapter_chunks[:5]:  # Use top 5 chunks as representatives
        similar = self.vectordb.search(
            chunk['text'],
            limit=20,
            score_threshold=0.6
        )

        for result in similar:
            other_ch = result['metadata'].get('chapter_number')
            if other_ch and other_ch != chapter_num:
                if other_ch not in connections:
                    connections[other_ch] = []
                connections[other_ch].append({
                    'similarity_score': result['score'],
                    'excerpt': result['text'][:150]
                })

    # Sort by connection strength
    sorted_connections = sorted(
        connections.items(),
        key=lambda x: sum(c['similarity_score'] for c in x[1]),
        reverse=True
    )

    return {
        'source_chapter': chapter_num,
        'connected_chapters': [
            {
                'chapter': ch_num,
                'connection_strength': sum(c['similarity_score'] for c in chunks) / len(chunks),
                'examples': chunks[:2]
            }
            for ch_num, chunks in sorted_connections[:10]
        ]
    }
```

---

### Phase 1.2: Smart Quote & Fact Extraction Skill

**New files to create:**
- `src/skills/__init__.py`
- `src/skills/fact_extractor.py`

**Approach:**
During indexing, enhance chunks with metadata tags identifying:
- **Quotes**: Text in quotation marks with attribution
- **Statistics**: Numbers with units/context (percentages, dollar amounts, counts)
- **Definitions**: "X is defined as..." or "X refers to..."
- **Case studies**: Named examples ("In the case of...", "For example,...")

**Implementation:**
```python
# src/skills/fact_extractor.py
import re
from typing import Dict, Any, List

class FactExtractor:
    def __init__(self):
        # Regex patterns for fact types
        self.stat_pattern = r'\d+[\d,\.]*\s*(?:%|percent|billion|million|thousand|USD|dollars?)'
        self.quote_pattern = r'["\u201C]([^"\u201D]{20,200})["\u201D]'
        self.definition_pattern = r'(?:is defined as|refers to|means|is a type of)'

    def extract_facts(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract facts from text chunk"""
        facts = []

        # Find statistics
        for match in re.finditer(self.stat_pattern, text):
            facts.append({
                'type': 'statistic',
                'value': match.group(),
                'context': text[max(0, match.start()-50):match.end()+50],
                **metadata
            })

        # Find quotes
        for match in re.finditer(self.quote_pattern, text):
            facts.append({
                'type': 'quote',
                'value': match.group(1),
                'context': text[max(0, match.start()-50):match.end()+50],
                **metadata
            })

        # Check for definitions
        if re.search(self.definition_pattern, text, re.IGNORECASE):
            facts.append({
                'type': 'definition',
                'value': text[:200],  # First 200 chars
                **metadata
            })

        return facts

# Integrate into indexing pipeline:
# In src/indexer/zotero_indexer.py and scrivener_indexer.py:
# After chunking, run fact extraction and add to chunk metadata
```

**MCP Tool:**
```python
# Add to src/mcp_server.py:
{
    "name": "find_compelling_facts",
    "description": "Find notable quotes, statistics, and facts",
    "inputSchema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "fact_type": {"type": "string", "enum": ["quote", "statistic", "definition", "any"]},
            "chapter_number": {"type": "integer"}
        },
        "required": ["topic"]
    }
}

async def _find_facts(topic, fact_type='any', chapter_number=None):
    # Search for topic
    filters = {}
    if chapter_number:
        filters['chapter_number'] = chapter_number
    if fact_type != 'any':
        filters['fact_type'] = fact_type

    results = self.vectordb.search(topic, filters=filters, limit=30)

    # Filter to only chunks with fact metadata
    facts = [r for r in results if 'fact_type' in r['metadata']]

    return {
        'topic': topic,
        'fact_count': len(facts),
        'facts': facts[:20]
    }
```

---

### Phase 1.3: Citation Extraction & Management

**Files to modify:**
- `src/indexer/zotero_indexer.py` - enhance to extract full metadata
- Create: `src/skills/citation_manager.py`

**Zotero metadata to extract:**
```python
# In zotero_indexer.py:
def get_item_metadata(self, item_id: int) -> Dict[str, Any]:
    """Get full bibliographic metadata for Zotero item"""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    # Query item fields (title, author, date, publication, etc.)
    query = """
        SELECT f.fieldName, v.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues v ON id.valueID = v.valueID
        WHERE id.itemID = ?
    """
    cursor.execute(query, (item_id,))

    metadata = dict(cursor.fetchall())

    # Get creators (authors, editors)
    query = """
        SELECT ct.creatorType, c.firstName, c.lastName
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
        JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
        WHERE ic.itemID = ?
        ORDER BY ic.orderIndex
    """
    cursor.execute(query, (item_id,))
    metadata['creators'] = cursor.fetchall()

    conn.close()
    return metadata
```

**MCP Tool:**
```python
{
    "name": "get_citations_for_chapter",
    "description": "Get formatted citations for a chapter's sources",
    "inputSchema": {
        "type": "object",
        "properties": {
            "chapter_number": {"type": "integer"},
            "style": {"type": "string", "enum": ["chicago", "apa", "mla"], "default": "chicago"}
        },
        "required": ["chapter_number"]
    }
}
```

---

## Implementation Notes

- Each skill should be a separate Python module in `src/skills/`
- Skills expose functionality via MCP tools registered in `src/mcp_server.py`
- Skills can share access to vectordb and indexers
- Fact extraction runs during indexing to enrich chunk metadata
- Citation data stored in vector DB payload for each chunk
