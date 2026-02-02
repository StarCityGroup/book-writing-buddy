# Check Sync Workflow

**Name:** `check_sync_workflow`

**Description:** Check sync status and provide detailed recommendations

**Parameters:** None

**Workflow Steps:**

1. Use `check_sync` to identify mismatches between outline, Zotero, and Scrivener
2. Use `list_chapters` to verify the definitive Scrivener structure
3. Use `get_chapter_info` for each chapter to check what content is indexed
4. Analyze the sync report to identify specific issues:
   - Chapters in outline but missing from Scrivener
   - Chapters in Scrivener but not in outline
   - Zotero collections that don't match chapter structure
5. Provide specific recommendations for each issue found

**Example Usage:**
- "Check if my chapters are in sync"
- "Are there any mismatches between my sources?"
- "Verify sync status"
