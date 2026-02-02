# Export Research

**Name:** `export_research`

**Description:** Generate formatted research summary or bibliography

**Parameters:**
- `chapter` (int, required): Chapter number
- `output_type` (str, required): "summary" or "bibliography"

**Workflow Steps:**

1. Use `get_chapter_info` to verify chapter exists and get basic information
2. If output_type is "summary":
   - Use `export_chapter_summary` with format="markdown"
   - Include key sources, themes, and research overview
3. If output_type is "bibliography":
   - Use `generate_bibliography` with style from user preference (default: APA)
   - Format citations properly
4. Present formatted output ready for user consumption

**Example Usage:**
- "Export a research summary for chapter 7"
- "Generate an APA bibliography for chapter 4"
- "Create a research brief for chapter 5 in markdown"
- "Show me citations for chapter 9 in MLA format"
