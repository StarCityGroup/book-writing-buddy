# Testing the New Functionality

This guide helps you test the Scrivener parser, context loading, and sync checker.

## Quick Test - Run Everything

```bash
# Run comprehensive test suite
uv run python scripts/test_all.py
```

This will test:
1. **Scrivener Parser** - Reads chapter structure from your .scrivx file
2. **Context Loading** - Combines Scrivener + outline.txt into system prompt
3. **Sync Checker** - Detects mismatches between sources
4. **Check-Sync Skill** - Verifies the Claude Code skill works

## Individual Component Tests

### Test 1: Scrivener Parser

```bash
# Run parser test
uv run python tests/test_scrivener_parser.py
```

**What it tests:**
- Can parse your .scrivx file
- Extracts chapter numbers and titles
- Handles various chapter naming formats
- Formats structure as readable text

**Expected output:**
```
✅ Parser initialization
✅ Chapter structure extraction
📚 Project: FIREWALL
📖 Found 27 chapters
  Chapter 1: the mangrove and the space mirror
  Chapter 2: adaptation shock
  ...
```

### Test 2: Context Loading

```bash
# Test loading context from both sources
uv run python tests/test_context_loading.py
```

**What it tests:**
- Loads Scrivener structure dynamically
- Loads outline.txt content
- Combines both into agent context
- Handles missing files gracefully

**Expected output:**
```
✅ Scrivener structure found in context
✅ Book outline found in context
📋 Generated Context Length: 5432
```

### Test 3: Sync Checker

```bash
# Test sync detection
uv run python tests/test_sync_checker.py
```

**What it tests:**
- Extracts chapters from all three sources
- Detects mismatches
- Generates recommendations
- Formats readable reports

**Expected output:**
```
📊 Sync Status: ✅ In Sync
📚 Chapter Counts:
  Scrivener: 27
  Zotero: 27
  Outline: 27
```

### Test 4: Check-Sync Skill

```bash
# Test the Claude Code skill directly
uv run .claude/skills/check-sync/main.py
```

**What it tests:**
- Skill can be executed
- Produces valid output
- Reports sync status

**Expected output:**
```
# Sync Status Report

✓ **All sources are in sync**

## Chapter Counts
- Scrivener: 27 chapters
- Zotero: 27 chapters
- Outline: 27 chapters
```

## Manual Testing with Claude Code

Start Claude Code and try these queries:

```bash
claude
```

Then ask:

### Test Context Loading
```
"What chapters does my book have?"
"Tell me about the structure of my manuscript"
```

The agent should describe your actual Scrivener structure.

### Test Sync Detection
```
"Check if my chapters are in sync"
"Run the check-sync skill"
```

Should report alignment status and any mismatches.

### Test Graceful Handling
```
"Search for research about chapter 50"
```

Should handle gracefully (since chapter 50 doesn't exist), ask for clarification.

## Testing Sync Detection

To test that the system detects mismatches:

### Scenario 1: Add Chapter to Scrivener Only

1. Add a new chapter in Scrivener (e.g., "28. Conclusion")
2. Don't update Zotero or outline.txt
3. Run sync check:
   ```bash
   uv run .claude/skills/check-sync/main.py
   ```
4. Should report: "Chapter 28 exists in Scrivener but has no Zotero collection"

### Scenario 2: Remove Chapter from Scrivener

1. Delete a chapter from Scrivener
2. Keep it in Zotero and outline.txt
3. Run sync check
4. Should report: "Chapter X exists in outline/Zotero but not in Scrivener"

### Scenario 3: Everything in Sync

1. Ensure all chapter numbers match across sources
2. Run sync check
3. Should report: "✓ All sources are in sync"

## Troubleshooting Tests

### "SCRIVENER_PROJECT_PATH not configured"

Ensure `.env` file has the correct path:
```bash
SCRIVENER_PROJECT_PATH=/Users/yourusername/Dropbox/Apps/Scrivener/FIREWALL.scriv
```

### "Could not parse Scrivener structure"

Check that:
- Path points to a `.scriv` directory
- `.scrivx` file exists inside (e.g., `FIREWALL.scriv/FIREWALL.scrivx`)
- XML is valid (not corrupted)

### "No chapters found"

Check your Scrivener structure:
- Are chapters numbered? (e.g., "1. Title" or "Chapter 1")
- Are they in the Binder (not in Trash)?

### "Qdrant connection refused"

Some tests need Qdrant running:
```bash
docker compose up -d
```

## Test Coverage

What we're testing:

✅ Scrivener .scrivx file parsing
✅ Chapter number extraction (multiple formats)
✅ Hierarchical structure parsing (Parts → Chapters)
✅ Dynamic context loading
✅ Combining Scrivener + outline.txt
✅ Handling missing files gracefully
✅ Sync detection across three sources
✅ Mismatch identification
✅ Recommendation generation
✅ Report formatting
✅ Skill execution

## Expected Test Results

All tests should pass if:
- `.env` is configured with valid paths
- Scrivener project exists and is valid
- `data/outline.txt` exists
- Qdrant is running (for sync checker)
- Dependencies are installed (`uv sync`)

## Continuous Testing

Run tests after making changes:

```bash
# After modifying parser
uv run python tests/test_scrivener_parser.py

# After changing context loading
uv run python tests/test_context_loading.py

# After updating sync logic
uv run python tests/test_sync_checker.py

# Run everything
uv run python scripts/test_all.py
```

## Integration Test

The ultimate test is using it with Claude Code:

1. Start Claude Code: `claude`
2. Ask about chapter structure: "What chapters does my book have?"
3. Ask it to check sync: "Are my chapters in sync?"
4. Ask for research help: "Find research about climate adaptation in chapter 3"

The agent should:
- Know your actual chapter structure from Scrivener
- Understand themes from outline.txt
- Detect if things are out of sync
- Ask clarifying questions when ambiguous
- Work gracefully even with missing data
