# Research Timeline

**Name:** `research_timeline`

**Description:** Analyze when research materials were collected and identify collection patterns or staleness

**Parameters:**
- `chapter` (int, optional): Specific chapter to analyze. Default: all

**Workflow Steps:**

1. Use `list_chapters` to get the full chapter structure
2. For each chapter (or the specified chapter):
   - Use `get_chapter_info` to get source metadata including dates
   - Use `search_research` to sample recent additions
3. Build a timeline showing:
   - When sources were added to each chapter's collection
   - Periods of active research vs. gaps
   - Most recently added materials
   - Oldest sources that may need updating
4. Identify patterns:
   - If chapters with recent deadlines lack recent research
   - If some chapters haven't had new sources in a long time
   - If research is clustered (burst of activity then nothing)
5. Provide recommendations:
   - Chapters needing fresh research
   - Sources that may be outdated
   - Suggested research schedule based on patterns

**Example Usage:**
- "Show me a research timeline for chapter 9"
- "When was the last time I added research for each chapter?"
- "Which chapters have stale research?"
- "Research collection patterns across the book"
