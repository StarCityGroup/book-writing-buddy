# Source Quality Check

**Name:** `source_quality_check`

**Description:** Evaluate source diversity, identify over-relied sources, and assess research quality for a chapter

**Parameters:**
- `chapter` (int, required): Chapter number to check

**Workflow Steps:**

1. Use `get_chapter_info` to get source counts and basic statistics
2. Use `analyze_source_diversity` to calculate diversity index and source type breakdown
3. Use `identify_key_sources` to find the most-referenced sources
4. Use `search_research` with source_type="zotero" to sample actual source content
5. Evaluate research quality:
   - If diversity index is low, identify which source types are missing
   - If one source dominates, flag over-reliance risk
   - Check for balance between academic, journalistic, and primary sources
6. Use `compare_chapters` to see how this chapter's research compares to similar chapters
7. Provide a quality assessment with:
   - Diversity score and interpretation
   - Source type breakdown with recommendations
   - Over-relied sources to watch
   - Suggested source types to add
   - Comparison to other chapters

**Example Usage:**
- "Check source quality for chapter 9"
- "Am I relying too heavily on certain sources in chapter 5?"
- "How diverse are my sources for chapter 3?"
- "Source balance check for chapter 12"
