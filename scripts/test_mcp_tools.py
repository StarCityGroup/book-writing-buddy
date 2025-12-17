#!/usr/bin/env python3
"""
Simple test script for MCP tools.
Tests each tool by sending MCP protocol messages.
"""

import json
import subprocess
import sys


def send_mcp_request(tool_name, arguments=None):
    """Send an MCP request to the server"""
    if arguments is None:
        arguments = {}

    # MCP initialize request
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    # MCP tool call request
    tool_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    # Send both requests
    requests = json.dumps(initialize_request) + "\n" + json.dumps(tool_request) + "\n"

    # Execute via docker
    proc = subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            "-e",
            "MCP_MODE=stdio",
            "book-research-mcp",
            "python",
            "src/mcp_server.py",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = proc.communicate(input=requests, timeout=30)

    if stderr:
        print(f"STDERR: {stderr}", file=sys.stderr)

    # Parse responses (one per line)
    responses = []
    for line in stdout.strip().split("\n"):
        if line:
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Failed to parse: {line}", file=sys.stderr)

    return responses


def test_search_research():
    """Test search_research tool"""
    print("\n=== Testing search_research ===")
    responses = send_mcp_request(
        "search_research", {"query": "infrastructure resilience", "limit": 3}
    )

    for resp in responses:
        if resp.get("id") == 2:  # Tool response
            result = resp.get("result")
            if result:
                content = result.get("content", [])
                if content:
                    data = json.loads(content[0].get("text", "{}"))
                    print(f"Query: {data.get('query')}")
                    print(f"Results: {data.get('count')}")
                    print("Sample excerpts:")
                    for r in data.get("results", [])[:2]:
                        print(f"  - {r.get('text', '')[:100]}...")


def test_prepare_chapter():
    """Test prepare_chapter tool"""
    print("\n=== Testing prepare_chapter ===")
    responses = send_mcp_request("prepare_chapter", {"chapter_number": 9})

    for resp in responses:
        if resp.get("id") == 2:
            result = resp.get("result")
            if result:
                content = result.get("content", [])
                if content:
                    data = json.loads(content[0].get("text", "{}"))
                    print(f"Chapter: {data.get('chapter_number')}")
                    print(f"Collection: {data.get('collection_name')}")
                    print(f"Zotero sources: {data.get('zotero_sources')}")
                    print(f"Scrivener sections: {data.get('scrivener_sections')}")


def test_analyze_theme():
    """Test analyze_theme_across_manuscript tool"""
    print("\n=== Testing analyze_theme_across_manuscript ===")
    responses = send_mcp_request(
        "analyze_theme_across_manuscript", {"theme": "adaptation"}
    )

    for resp in responses:
        if resp.get("id") == 2:
            result = resp.get("result")
            if result:
                content = result.get("content", [])
                if content:
                    data = json.loads(content[0].get("text", "{}"))
                    print(f"Theme: {data.get('theme')}")
                    print(f"Chapters found: {data.get('chapters_found')}")
                    print(f"Total mentions: {data.get('total_mentions')}")
                    print("Chapters with theme:")
                    for ch in data.get("by_chapter", [])[:5]:
                        print(
                            f"  - Chapter {ch.get('chapter')}: {ch.get('occurrences')} occurrences"
                        )


def test_find_connections():
    """Test find_cross_chapter_connections tool"""
    print("\n=== Testing find_cross_chapter_connections ===")
    responses = send_mcp_request(
        "find_cross_chapter_connections", {"chapter_number": 5}
    )

    for resp in responses:
        if resp.get("id") == 2:
            result = resp.get("result")
            if result:
                content = result.get("content", [])
                if content:
                    data = json.loads(content[0].get("text", "{}"))
                    print(f"Source chapter: {data.get('source_chapter')}")
                    print("Connected chapters:")
                    for conn in data.get("connected_chapters", [])[:5]:
                        print(
                            f"  - Chapter {conn.get('chapter')}: strength {conn.get('connection_strength'):.3f}"
                        )


if __name__ == "__main__":
    print("Testing MCP Tools...")

    try:
        test_search_research()
        test_prepare_chapter()
        test_analyze_theme()
        test_find_connections()
        print("\n✅ All tests completed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}", file=sys.stderr)
        sys.exit(1)
