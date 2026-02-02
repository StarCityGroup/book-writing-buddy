# Research Gaps

**Name:** `research_gaps`

**Description:** Identify chapters that need more research materials

**Parameters:** None

**Workflow Steps:**

1. Use `list_chapters` to get all chapter numbers and titles
2. For each chapter:
   - Use `get_chapter_info` to get source counts and statistics
   - Record: chapter number, title, Zotero count, Scrivener count
3. Use `compare_chapters` to analyze density differences between chapters
4. Identify chapters with significantly fewer sources than average
5. Provide recommendations for filling gaps, including:
   - Which chapters need more research
   - What types of sources might be needed
   - How they compare to well-researched chapters

**Example Usage:**
- "Which chapters need more research?"
- "Analyze research gaps across the manuscript"
- "Show me chapters that are under-researched"
