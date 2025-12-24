# Agent Architecture V2 - Simplified ReAct Design

## Overview

Complete redesign from complex multi-node state machine to simple ReAct agent with tool access.

## Key Improvements

### Before (V1)
- ❌ 19 specialized nodes with complex routing
- ❌ 22 state fields that needed maintenance
- ❌ 16 formatting methods
- ❌ Rigid workflow with many edge cases
- ❌ State explosion and missing field bugs
- ❌ Agent couldn't flexibly combine queries

### After (V2)
- ✅ 1 ReAct agent node
- ✅ 12 flexible tools agent can use
- ✅ No state management needed (conversation history only)
- ✅ Simple linear workflow
- ✅ Agent decides what tools to use and when
- ✅ Can loop and use multiple tools as needed

## New Architecture

```
┌─────────────────────────────────────────┐
│ User Query                              │
└──────────────┬──────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │  ReAct Agent │ ◄──┐
        │              │    │
        │  • Plan      │    │ Tool Loop
        │  • Use Tools │    │ (max 15 iterations)
        │  • Analyze   │ ───┘
        │  • Respond   │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │   Response   │
        └──────────────┘
```

## Tools Provided (12 total)

### Core Research (6 tools)
1. **search_research** - Semantic search with optional chapter filter
2. **get_annotations** - Zotero highlights and notes
3. **get_chapter_info** - Detailed chapter statistics
4. **list_chapters** - Book structure from Scrivener
5. **check_sync** - Alignment status between sources
6. **get_scrivener_summary** - Indexing breakdown

### Analysis (4 tools)
7. **compare_chapters** - Compare research density
8. **find_cross_chapter_themes** - Track themes across chapters
9. **analyze_source_diversity** - Check source type balance
10. **identify_key_sources** - Find most-cited sources

### Export (2 tools)
11. **export_chapter_summary** - Generate research brief
12. **generate_bibliography** - Create citation list (APA/MLA/Chicago)

## How It Works

### 1. User Query
```
User: "Track the theme 'infrastructure failure' across all chapters"
```

### 2. Agent Plans
```
Thought: I need to search for this theme across all chapters.
I'll use find_cross_chapter_themes to track where it appears.
```

### 3. Agent Uses Tools
```
Action: find_cross_chapter_themes
Action Input: {"keyword": "infrastructure failure"}
Observation: [Results showing chapters 3, 9, 11, 14, 19, 26 mention this theme]
```

### 4. Agent May Use More Tools
```
Thought: Let me get more details on chapter 9 since it has the most mentions.
Action: search_research
Action Input: {"query": "infrastructure failure", "chapter": 9}
Observation: [Detailed results from chapter 9]
```

### 5. Agent Responds
```
Thought: I have enough information now.
Final Answer: [Comprehensive analysis with citations]
```

## Implementation Details

### File Structure
```
src/
├── tools.py          # LangChain tool definitions (NEW)
├── agent_v2.py       # Simplified ReAct agent (NEW)
├── cli.py            # Updated to use agent_v2
├── rag.py            # Unchanged - tools wrap these methods
└── [old files kept for reference]
```

### Tools Implementation (src/tools.py)

Each tool is a simple wrapper around BookRAG methods:

```python
@tool
def search_research(query: str, chapter: Optional[int] = None, limit: int = 20) -> dict:
    """Search semantically through research materials."""
    rag = get_rag()
    results = rag.search(query=query, filters=filters, limit=limit)
    return formatted_results
```

Tools use `@tool` decorator so LangChain can:
- Parse parameters from natural language
- Provide docstrings as tool descriptions
- Handle errors gracefully
- Format results for the agent

### Agent Implementation (src/agent_v2.py)

Uses LangChain's ReAct pattern:
- **Prompt template** with book context and tool descriptions
- **Agent loop** that decides what tools to call
- **Max 15 iterations** to prevent infinite loops
- **3 minute timeout** for safety

### System Prompt

The agent receives:
1. **Full book context** - Scrivener structure + outline.txt
2. **Tool descriptions** - Auto-generated from @tool docstrings
3. **Response guidelines** - How to structure answers
4. **Sync handling** - How to deal with missing data

## Benefits

### Simplicity
- **90% less code** in agent logic
- **No state management** bugs
- **No routing logic** to maintain
- **No formatting methods** needed

### Flexibility
- Agent can **combine tools creatively**
- Can use **same tool multiple times**
- Can **adjust strategy** based on results
- Handles **edge cases naturally**

### Maintainability
- **Add new tools** by adding one function
- **No workflow updates** needed
- **No state field additions** needed
- **No routing changes** needed

### Observability
- **Verbose mode** shows tool usage
- **Clear thought process** in logs
- **Easy to debug** linear flow

## Migration Notes

### What Changed
- `src/agent.py` → Not used (kept for reference)
- `src/nodes.py` → Not used (kept for reference)
- `src/state.py` → Not used (kept for reference)
- `src/cli.py` → Updated to use `agent_v2`

### What Stayed
- `src/rag.py` - Unchanged, tools wrap these methods
- All indexing code - Unchanged
- Vector database - Unchanged
- Configuration - Unchanged

### Backward Compatibility
- Old agent files kept in repo (not imported)
- Can switch back by changing import in cli.py
- No data migration needed

## Testing

### Basic Test
```bash
uv run main.py
```

### Test Cases
1. **Simple search**: "Find sources about urban heat islands"
2. **Cross-chapter analysis**: "Track the theme 'resilience' across all chapters"
3. **Comparison**: "Compare chapters 5 and 9"
4. **Sync check**: "Check if my sources are in sync"
5. **Complex query**: "What are the key sources for chapter 3 and how diverse are they?"

### Expected Behavior
- Agent uses 1-5 tools per query
- Shows thought process in verbose mode
- Combines tools intelligently
- Handles missing data gracefully

## Performance

### Speed
- **First query**: ~5-10 seconds (includes tool setup)
- **Subsequent queries**: ~2-5 seconds per tool call
- **Multi-tool queries**: Linear with number of tools used

### Token Usage
- **System prompt**: ~2K tokens (book context)
- **Per tool call**: ~500-1K tokens
- **Typical query**: 3-8K tokens total

## Future Enhancements

### Easy Additions
1. **Memory** - Add conversation summarization for context
2. **Streaming** - Stream agent thoughts and tool results
3. **Caching** - Cache common queries
4. **More tools** - Just add @tool functions

### Advanced Features
1. **Multi-agent** - Spawn specialized sub-agents
2. **Planning** - Add explicit planning step before tools
3. **Reflection** - Self-critique and improve responses
4. **Learning** - Learn from user feedback

## Troubleshooting

### Agent loops infinitely
- Check max_iterations in agent_v2.py (default 15)
- Check tool return types (must be JSON-serializable)

### Agent doesn't use tools
- Check tool docstrings are clear
- Check prompt template formatting
- Enable verbose mode to see reasoning

### Tools return errors
- Check BookRAG methods are working
- Check vector database connection
- Check environment variables (.env)

### No results from search
- Verify data is indexed (use /knowledge command)
- Check chapter numbers match Scrivener
- Try broader search terms

## Comparison Table

| Aspect | V1 (Old) | V2 (New) |
|--------|----------|----------|
| **Nodes** | 19 | 1 |
| **Tools** | 0 (built into nodes) | 12 |
| **State fields** | 22 | 0 (just history) |
| **Routing logic** | 17 cases | 0 (agent decides) |
| **Code complexity** | High | Low |
| **Flexibility** | Rigid | High |
| **Debugging** | Hard | Easy |
| **Extensibility** | Hard | Easy |
| **Maintainability** | Hard | Easy |

## Conclusion

The V2 architecture is dramatically simpler while being more powerful and flexible. By giving the agent **tools** instead of **predefined workflows**, we enable it to:

- Plan its own research strategy
- Combine tools in creative ways
- Handle edge cases naturally
- Adapt to different query types

This is the right architecture for a research assistant.
