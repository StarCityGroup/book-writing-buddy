# Deep Chapter Analysis

**Name:** `deep_chapter_analysis`

**Description:** Full deep-dive analysis combining research review, source evaluation, gap identification, and structured export

**Parameters:**
- `chapter` (int, required): Chapter number to analyze
- `format` (str, optional): Output format - "markdown" or "brief". Default: markdown

**Workflow Steps:**

1. Use `get_chapter_info` to get chapter statistics and metadata
2. Use `search_research` with source_type="zotero" to find all published research for this chapter
3. Use `search_research` with source_type="scrivener" to review existing manuscript content
4. Use `get_annotations` to pull all Zotero highlights and margin notes
5. Use `analyze_source_diversity` to evaluate balance of source types
6. Use `identify_key_sources` to find the most-referenced materials
7. Use `find_cross_chapter_themes` to identify themes shared with other chapters
8. Synthesize all findings into a structured analysis covering:
   - Research landscape (what sources exist, how diverse)
   - Key arguments and evidence available
   - What's already drafted vs. what needs writing
   - Cross-chapter connections to leverage
   - Specific gaps that need additional research
9. Use `export_chapter_summary` to generate the formatted output

**Example Usage:**
- "Do a deep dive on chapter 9"
- "Give me a full deep analysis of chapter 5 with everything you can find"
- "Comprehensive research review for chapter 12"
