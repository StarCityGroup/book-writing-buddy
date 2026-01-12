# Claude Agent SDK Migration Assessment

**Date**: 2026-01-08
**Status**: Feasibility Analysis Complete
**Update**: 2026-01-09 - Removed local inference fallback (too slow for this use case)

## Executive Summary

**Verdict**: ✅ **FEASIBLE** - Migration is technically possible with moderate effort (8-14 hours)

The current LangGraph-based agent can be successfully migrated to the Claude Agent SDK. The migration would result in simpler, cleaner code with better conversation management, but requires rewriting all 12 custom tools and introduces a new dependency (Claude Code CLI).

**Important**: This migration assumes cloud API access. Local inference via Ollama (OFFLINE_AGENT_MODEL) is being **removed** from consideration as it's too slow for this use case.

## Current Architecture

### Tech Stack
- **LangGraph**: `create_react_agent()` for ReAct agent loop
- **LangChain**: Tool definitions and OpenAI integration
- **BookRAG**: Vector database operations (Qdrant) and research methods
- **12 Custom Tools**: All wrapping BookRAG methods
- **Rich CLI**: Interactive terminal interface
- **LiteLLM Proxy**: OpenAI-compatible API router for cloud Claude models (Cornell hosted)

### File Structure
```
src/
├── agent_v2.py          # LangGraph ReAct agent creation
├── tools.py             # 12 LangChain tools wrapping BookRAG
├── rag.py               # BookRAG class with all research methods
├── cli.py               # Rich CLI with conversation management
└── vectordb/
    └── client.py        # Qdrant vector database client
```

### Current Tools (12 total)
1. `search_research` - Semantic search with filters
2. `get_annotations` - Zotero highlights/notes
3. `get_chapter_info` - Chapter statistics
4. `list_chapters` - Scrivener chapter list
5. `check_sync` - Sync status between sources
6. `get_scrivener_summary` - Indexing breakdown
7. `compare_chapters` - Research density comparison
8. `find_cross_chapter_themes` - Theme tracking
9. `analyze_source_diversity` - Source type analysis
10. `identify_key_sources` - Most-cited sources
11. `export_chapter_summary` - Research brief generation
12. `generate_bibliography` - Citation formatting

## Claude Agent SDK Overview

### What It Is
The Claude Agent SDK is Anthropic's official Python/TypeScript library for building autonomous AI agents. It provides:
- Built-in tools (Read, Write, Edit, Bash, Grep, Glob, WebSearch, etc.)
- Custom tool support via MCP (Model Context Protocol)
- Automatic ReAct loop handling
- Built-in session/conversation management
- Hooks for behavior interception
- Official support from Anthropic

### Key Capabilities

#### Built-in Tools
The SDK includes ~20+ built-in tools for common operations:
- File operations: Read, Write, Edit, Glob, Grep
- Shell: Bash, BashOutput, KillBash
- Web: WebSearch, WebFetch
- User interaction: AskUserQuestion
- Task management: TodoWrite, Task (subagents)
- MCP: ListMcpResources, ReadMcpResource

#### Custom Tools
Define custom tools using SDK's `@tool` decorator:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("search_research", "Search semantically through research materials", {
    "query": str,
    "chapter": int | None,
    "source_type": str | None,
    "limit": int
})
async def search_research(args: dict) -> dict:
    rag = get_rag()
    results = rag.search(
        query=args["query"],
        filters={"chapter_number": args.get("chapter")} if args.get("chapter") else None,
        limit=args.get("limit", 20)
    )
    return {"content": [{"type": "text", "text": str(results)}]}

# Create MCP server with tools
research_server = create_sdk_mcp_server(
    name="research",
    version="1.0.0",
    tools=[search_research, get_annotations, ...]
)
```

#### Agent Management
Two approaches:

**Option 1: Simple queries** (one-off)
```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Analyze chapter 5 research",
    options=ClaudeAgentOptions(
        mcp_servers={"research": research_server},
        allowed_tools=["mcp__research__search_research"]
    )
):
    print(message)
```

**Option 2: ClaudeSDKClient** (continuous conversation)
```python
from claude_agent_sdk import ClaudeSDKClient

async with ClaudeSDKClient(options=options) as client:
    await client.query("What's in chapter 5?")
    async for msg in client.receive_response():
        print(msg)

    # Follow-up in same conversation
    await client.query("Compare that to chapter 9")
    async for msg in client.receive_response():
        print(msg)
```

## Migration Analysis

### What Would Change

#### Dependencies
**Remove:**
```toml
langchain>=1.1.3
langchain-openai>=1.1.3
langgraph>=1.0.5
```

**Add:**
```toml
claude-agent-sdk>=1.0.0
```

**Plus:** Users need to install Claude Code CLI:
```bash
curl -fsSL https://claude.ai/install.sh | bash
# or
npm install -g @anthropic-ai/claude-code
```

#### Environment Configuration Changes

**Remove from `.env`:**
```bash
OFFLINE_AGENT_MODEL=qwen2.5:14b-instruct  # Local inference too slow, not supported
```

**Keep (for LiteLLM proxy routing):**
```bash
OPENAI_API_KEY="..."
OPENAI_API_BASE="https://api.ai.it.cornell.edu"
DEFAULT_MODEL=anthropic.claude-4.5-sonnet
MODEL_GOOD=anthropic.claude-4.5-haiku
MODEL_BETTER=anthropic.claude-4.5-sonnet
MODEL_BEST=anthropic.claude-4.5-opus
```

**Note**: The Claude Agent SDK can work with LiteLLM proxy by configuring the API key and base URL via environment variables. The SDK will route through your Cornell LiteLLM proxy just like the current setup.

#### Tool Definitions (12 tools to convert)

**Current format (LangChain):**
```python
from langchain_core.tools import tool

@tool
def search_research(query: str, chapter: Optional[int] = None, ...) -> dict:
    """Search semantically through research materials."""
    rag = get_rag()
    return rag.search(query=query, ...)
```

**New format (SDK MCP):**
```python
from claude_agent_sdk import tool

@tool("search_research", "Search semantically through research materials", {
    "query": str,
    "chapter": int | None,
    "source_type": str | None,
    "limit": int
})
async def search_research(args: dict[str, Any]) -> dict[str, Any]:
    """Search semantically through research materials."""
    rag = get_rag()
    results = rag.search(query=args["query"], ...)
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(results, indent=2)
        }]
    }
```

**Key differences:**
- SDK tools must be async
- Input is a dict, not named parameters
- Output must be `{"content": [{"type": "text", "text": "..."}]}`
- Schema definition is separate from function signature

#### Agent Creation

**Current (LangGraph):**
```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model=model_name, base_url=litellm_url, ...)
agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT
)

# Usage
result = agent.invoke({"messages": conversation_history})
```

**New (SDK):**
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    mcp_servers={"research": research_server},
    allowed_tools=["mcp__research__*"],  # All research tools
    model="claude-sonnet-4-5-20250514"
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(user_input)
    async for message in client.receive_response():
        # Handle message
        pass
```

#### CLI Conversation Loop

**Current approach:**
```python
# Manual conversation history management
self.conversation_history.append({"role": "user", "content": user_input})
result = self.agent.invoke({"messages": self.conversation_history})
last_message = result["messages"][-1]
self.conversation_history.append({"role": "assistant", "content": last_message.content})
```

**SDK approach:**
```python
# Built-in session management
async with ClaudeSDKClient(options=options) as client:
    # First query
    await client.query(user_input)
    async for message in client.receive_response():
        # Process response
        pass

    # Follow-up - SDK remembers context automatically
    await client.query(next_input)
    async for message in client.receive_response():
        # Process response
        pass
```

**Benefits:**
- No manual history management
- Built-in session persistence
- Can resume sessions by ID
- Less code, cleaner

#### Message Handling

**Current (LangChain messages):**
```python
from langchain_core.messages import HumanMessage, AIMessage

messages = result.get("messages", [])
last_message = messages[-1]
if hasattr(last_message, "content"):
    response = last_message.content
```

**New (SDK messages):**
```python
from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock

async for message in client.receive_response():
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)
            elif isinstance(block, ToolUseBlock):
                print(f"Using tool: {block.name}")
```

**Key differences:**
- Different message types (AssistantMessage vs AIMessage)
- Content is list of blocks (TextBlock, ToolUseBlock, etc.)
- More granular control over message parts

### What Would Stay the Same

✅ **BookRAG class** - No changes needed
✅ **Vector database** (Qdrant) - No changes needed
✅ **Indexer** - No changes needed (as requested)
✅ **Rich console UI** - Minimal changes
✅ **Environment variables** - Mostly the same (API key, paths)
✅ **Core research logic** - All BookRAG methods unchanged
✅ **Offline embeddings** - `sentence-transformers` model cache still works offline
✅ **LiteLLM proxy** - Can continue routing through Cornell proxy

**Note**: Only the agent (LLM inference) requires cloud API access. Vector embeddings remain fully local/offline.

## Detailed Migration Plan

### Phase 1: Setup (30 min)
1. Install Claude Code CLI
2. Add `claude-agent-sdk` to dependencies
3. Remove LangChain dependencies (`langchain`, `langchain-openai`, `langgraph`)
4. Remove `OFFLINE_AGENT_MODEL` from `.env` (local inference too slow)
5. Test basic SDK functionality with cloud API

### Phase 2: Tool Conversion (2-4 hours)
Convert all 12 tools from LangChain to SDK MCP format:

**For each tool:**
1. Convert function signature to `async def tool_name(args: dict)`
2. Change input from named params to dict access
3. Wrap output in `{"content": [{"type": "text", "text": "..."}]}`
4. Update schema definition to SDK format

**Example conversion:**

```python
# BEFORE (LangChain)
@tool
def search_research(
    query: str,
    chapter: Optional[int] = None,
    source_type: Optional[str] = None,
    limit: int = 20
) -> dict:
    """Search semantically through research materials."""
    rag = get_rag()
    filters = {}
    if chapter:
        filters["chapter_number"] = chapter
    if source_type:
        filters["source_type"] = source_type
    results = rag.search(query=query, filters=filters, limit=limit)
    return {"results": results}

# AFTER (SDK)
@tool(
    "search_research",
    "Search semantically through research materials",
    {
        "query": str,
        "chapter": int,  # Optional fields can be omitted from args
        "source_type": str,
        "limit": int
    }
)
async def search_research(args: dict[str, Any]) -> dict[str, Any]:
    """Search semantically through research materials."""
    rag = get_rag()
    filters = {}
    if args.get("chapter"):
        filters["chapter_number"] = args["chapter"]
    if args.get("source_type"):
        filters["source_type"] = args["source_type"]

    results = rag.search(
        query=args["query"],
        filters=filters if filters else None,
        limit=args.get("limit", 20)
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({"results": results}, indent=2)
        }]
    }
```

**Create MCP server:**
```python
# tools.py

research_server = create_sdk_mcp_server(
    name="research",
    version="1.0.0",
    tools=[
        search_research,
        get_annotations,
        get_chapter_info,
        list_chapters,
        check_sync,
        get_scrivener_summary,
        compare_chapters,
        find_cross_chapter_themes,
        analyze_source_diversity,
        identify_key_sources,
        export_chapter_summary,
        generate_bibliography,
    ]
)
```

### Phase 3: Agent Refactoring (2-3 hours)

**Replace `agent_v2.py`:**

```python
"""Book research agent using Claude Agent SDK."""

import os
from claude_agent_sdk import ClaudeAgentOptions
from .tools import research_server

def load_book_context() -> str:
    """Load book context from Scrivener structure and outline.txt."""
    # Same as before
    ...

BOOK_CONTEXT = load_book_context()

SYSTEM_PROMPT = f"""You are an AI research assistant helping an author analyze their book research materials.

# Your Capabilities

You have DIRECT ACCESS to a vector database containing:
- **6,378+ indexed chunks** from Zotero research library and Scrivener manuscript
...

{BOOK_CONTEXT}
"""

def create_agent_options() -> ClaudeAgentOptions:
    """Create Claude Agent SDK options."""
    model_name = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5-20250514")

    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"research": research_server},
        allowed_tools=[
            "mcp__research__search_research",
            "mcp__research__get_annotations",
            "mcp__research__get_chapter_info",
            "mcp__research__list_chapters",
            "mcp__research__check_sync",
            "mcp__research__get_scrivener_summary",
            "mcp__research__compare_chapters",
            "mcp__research__find_cross_chapter_themes",
            "mcp__research__analyze_source_diversity",
            "mcp__research__identify_key_sources",
            "mcp__research__export_chapter_summary",
            "mcp__research__generate_bibliography",
        ],
        model=model_name,
        permission_mode="bypassPermissions",  # Auto-approve tool use
    )
```

### Phase 4: CLI Updates (2-3 hours)

**Update `cli.py` to use ClaudeSDKClient:**

```python
class BookResearchChatCLI:
    def __init__(self):
        load_dotenv()
        self.console = get_console()
        self.options = create_agent_options()
        self.client = None  # ClaudeSDKClient instance
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        ...

    async def run_agent(self, user_input: str):
        """Run the agent with user input."""
        try:
            if self.client is None:
                # Create client on first use
                self.client = ClaudeSDKClient(self.options)
                await self.client.connect()

            # Send query
            with Status("[header]Researching...[/header]", ...):
                await self.client.query(user_input)

            # Collect response
            response_text = []
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text.append(block.text)

            response = "\n".join(response_text)
            if response:
                self.print_message("assistant", response)

        except Exception as e:
            self.console.print(f"\n[error]Error: {e}[/error]\n")

    async def run(self):
        """Run the interactive CLI."""
        # Test connection, check Qdrant, etc.
        ...

        while True:
            try:
                user_input = Prompt.ask("\n[user]You[/user]")

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    if self.handle_command(user_input):
                        break
                    continue

                # Run agent
                await self.run_agent(user_input)

            except KeyboardInterrupt:
                self.console.print("\n\n[warning]Use /exit to quit properly.[/warning]\n")
            except EOFError:
                break

        # Cleanup
        if self.client:
            await self.client.disconnect()
```

**Handle `/new` command:**
```python
elif command_lower == "/new":
    # Disconnect and reconnect for fresh session
    if self.client:
        await self.client.disconnect()
    self.client = None
    self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    self.console.print("\n[success]Started new research session.[/success]\n")
```

### Phase 5: Testing (2-4 hours)

**Test all features:**
1. Basic queries - "What's in chapter 5?"
2. All 12 tools - verify each tool works correctly
3. Multi-turn conversations - ensure context is preserved
4. CLI commands - /help, /new, /settings, /knowledge, etc.
5. Model switching - /model good/better/best
6. Re-indexing - /reindex all/zotero/scrivener
7. Error handling - connection failures, invalid queries
8. Edge cases - empty results, malformed inputs

**Regression testing:**
- Compare outputs before/after migration
- Verify all existing functionality still works
- Check performance (may be slightly different)

## Pros and Cons

### Advantages ✅

1. **Simpler codebase**
   - Less boilerplate code
   - No manual agent loop management
   - Built-in conversation handling

2. **Better conversation management**
   - Automatic session persistence
   - Can resume sessions by ID
   - Built-in context management

3. **Official support**
   - Maintained by Anthropic
   - Better documentation
   - Guaranteed compatibility with Claude updates

4. **Cleaner architecture**
   - Less abstraction layers (no LangChain/LangGraph)
   - Direct Claude API integration
   - More transparent behavior

5. **Built-in features**
   - Hooks for logging/validation
   - File checkpointing
   - Permission management
   - Subagents support

6. **Future-proof**
   - Official SDK will track Claude capabilities
   - Access to latest Claude features
   - Better long-term support

### Disadvantages ❌

1. **New dependency (Claude Code CLI)**
   - Users must install additional binary
   - Extra setup step
   - Potential compatibility issues across platforms

2. **Migration effort**
   - 8-14 hours of work
   - Risk of introducing bugs
   - Team learning curve

3. **Different message format**
   - Need to update message handling code
   - Different debugging experience
   - Potential edge cases

4. **Process overhead**
   - SDK spawns CLI subprocess
   - Slightly more overhead vs direct API calls
   - Potential for IPC issues

5. **Less flexibility**
   - Locked into SDK's patterns
   - Can't use LangChain ecosystem
   - Harder to customize agent behavior

6. **API configuration**
   - Currently using Cornell LiteLLM proxy for cloud model routing
   - SDK uses environment variables (ANTHROPIC_API_KEY or OPENAI_API_KEY + OPENAI_API_BASE)
   - Should work with existing LiteLLM proxy setup without changes
   - **Note**: Local inference fallback (OFFLINE_AGENT_MODEL) removed - too slow for this use case

## Recommendations

### Option 1: Migrate to SDK ⭐ (Recommended if...)

**Choose this if you want:**
- Long-term maintainability with official tooling
- Simpler, cleaner codebase
- Better conversation/session management
- To reduce abstraction layers
- Official Anthropic support

**Effort:** 8-14 hours
**Risk:** Medium (well-documented SDK, but requires testing)

### Option 2: Keep LangGraph (Recommended if...)

**Choose this if you want:**
- Minimal risk and effort
- Current implementation is stable
- No new dependencies
- LangChain ecosystem integration
- Immediate deadline

**Effort:** 0 hours
**Risk:** Low (no changes)

### Option 3: Hybrid Approach

**Consider this if:**
- You want to test SDK before full migration
- You want to minimize risk
- You need gradual transition

**Approach:**
1. Keep current implementation working
2. Create SDK version in parallel (new branch)
3. Test thoroughly with real usage
4. Switch when confident

**Effort:** 10-16 hours (more testing)
**Risk:** Low (can rollback)

## My Recommendation

**I recommend Option 1 (Migrate to SDK)** for these reasons:

1. **Official tooling is better long-term** - You'll get better support, automatic compatibility with new Claude features, and guaranteed maintenance.

2. **Code will be cleaner** - The SDK handles a lot of boilerplate that you're currently managing manually. Your codebase will be simpler and easier to maintain.

3. **Conversation management is better** - Built-in session handling is superior to your current manual approach. This is a core feature of your app.

4. **Moderate effort is worthwhile** - 8-14 hours is reasonable for the benefits gained. You're not rewriting everything, just adapting to a new API.

5. **Project is early enough** - Better to migrate now than after more complexity is added.

6. **Cloud API is acceptable** - Since local inference is too slow anyway, requiring cloud API access (via Cornell LiteLLM proxy) is not a blocker.

**However**, do this migration as a **separate branch** with thorough testing before merging to main.

**Prerequisites:**
- ✅ Reliable internet connection
- ✅ Access to Cornell LiteLLM proxy (or Anthropic API directly)
- ✅ Willingness to install Claude Code CLI
- ✅ Cloud API acceptable (local inference removed)

## Implementation Timeline

**Week 1:**
- **Day 1-2**: Setup + Tool conversion (Phase 1-2)
- **Day 3-4**: Agent refactoring + CLI updates (Phase 3-4)
- **Day 5**: Testing + bug fixes (Phase 5)

**Week 2:**
- **Day 1-2**: More testing + edge cases
- **Day 3**: Documentation updates
- **Day 4**: Team review
- **Day 5**: Merge to main

## Next Steps

1. **Decide**: Choose Option 1, 2, or 3 above
2. **If migrating**: Create feature branch `feature/sdk-migration`
3. **Install SDK**: `uv add claude-agent-sdk` and install Claude Code CLI
4. **Clean up config**: Remove `OFFLINE_AGENT_MODEL` from `.env` (too slow)
5. **Follow phases**: Execute migration plan step-by-step (see above)
6. **Test thoroughly**: Don't skip testing phase
7. **Update docs**: Update README and CLAUDE.md with new setup instructions

## Questions to Consider

Before deciding, ask yourself:

1. **How important is long-term maintainability?**
   - High = Migrate
   - Low = Keep current

2. **Is the current implementation causing problems?**
   - Yes = Migrate
   - No = Keep current

3. **Do you have 8-14 hours to invest?**
   - Yes = Can migrate
   - No = Keep current

4. **Are you willing to add Claude Code CLI dependency?**
   - Yes = Can migrate
   - No = Keep current

5. **How risk-averse is your project?**
   - Low risk tolerance = Keep current or Hybrid
   - High risk tolerance = Migrate

6. **Do you have reliable cloud API access?**
   - Yes = Can migrate (local inference removed - too slow)
   - No = Keep current (or investigate faster local models first)

## References

- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude Agent SDK Python Docs](https://platform.claude.com/docs/en/agent-sdk/python)
- [Claude Agent SDK Quickstart](https://platform.claude.com/docs/en/agent-sdk/quickstart)
- [MCP Custom Tools](https://platform.claude.com/docs/en/agent-sdk/tools)
- [SDK GitHub - TypeScript](https://github.com/anthropics/claude-agent-sdk-typescript)
- [SDK GitHub - Python](https://github.com/anthropics/claude-agent-sdk-python)
