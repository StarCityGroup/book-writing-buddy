# Analyze Chapter

**Name:** `analyze_chapter`

**Description:** Comprehensive chapter analysis workflow: research, gaps, themes, sources

**Parameters:**
- `chapter` (int, required): Chapter number to analyze

**Workflow Steps:**

1. Use `get_chapter_info` to get basic statistics about the chapter
2. Use `search_research` to find key themes and concepts
3. Use `get_annotations` to review all Zotero highlights and notes
4. Use `analyze_source_diversity` to check if sources are balanced
5. Use `identify_key_sources` to find most-cited sources
6. Synthesize findings into comprehensive analysis with:
   - Key themes and arguments
   - Research strengths and gaps
   - Source diversity assessment
   - Recommendations for additional research

**Example Usage:**
- "Analyze chapter 9"
- "Run a full analysis on chapter 5"
- "Give me a comprehensive overview of chapter 3"
