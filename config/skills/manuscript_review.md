# Manuscript Review

**Name:** `manuscript_review`

**Description:** Review existing Scrivener manuscript content for a chapter, comparing drafts against research

**Parameters:**
- `chapter` (int, required): Chapter number to review

**Workflow Steps:**

1. Use `get_chapter_info` to get chapter metadata and content statistics
2. Use `get_scrivener_summary` to see what Scrivener documents exist for this chapter
3. Use `search_research` with source_type="scrivener" to read all manuscript content for this chapter
4. Use `search_research` with source_type="zotero" to find research that should be referenced
5. Use `get_annotations` to check for highlights and notes not yet incorporated
6. Compare what's drafted against what research is available:
   - Identify claims in the draft that lack source citations
   - Find research sources not yet referenced in the draft
   - Note areas where the draft could be strengthened with specific evidence
7. Provide a manuscript review summary with:
   - Draft completeness assessment
   - Unused research that could strengthen the chapter
   - Claims needing citations
   - Suggestions for revision priorities

**Example Usage:**
- "Review what I've written for chapter 7"
- "How does my draft for chapter 3 compare to my research?"
- "What research am I not using in chapter 11?"
