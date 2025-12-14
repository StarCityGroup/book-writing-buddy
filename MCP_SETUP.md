# MCP Server Setup Guide

This guide walks you through setting up the Model Context Protocol (MCP) servers needed for the book chapter analysis tool.

## Prerequisites

- Node.js installed (for MCP servers)
- Claude Desktop app installed
- Access to your local Zotero database
- Access to your Scrivener project files

## Required MCP Servers

### 1. Zotero MCP Server

This server provides access to your local Zotero database to read collections, items, notes, and annotations.

**Installation:**

```bash
npm install -g @modelcontextprotocol/server-zotero
```

### 2. Filesystem MCP Server

This server provides access to read files from your local filesystem, including Scrivener project files.

**Installation:**

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

## Configuration

### Locate Your Claude Config File

The Claude Desktop configuration file is located at:

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### Edit Configuration

Open `claude_desktop_config.json` and add the following (or merge with existing config):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-zotero"],
      "env": {
        "ZOTERO_DATA_DIR": "/Users/anthonytownsend/Zotero"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/anthonytownsend/Dropbox/Apps/Scrivener",
        "/Users/anthonytownsend/code/_dev/book-chapter-planner"
      ]
    }
  }
}
```

**Important Notes:**
- The `filesystem` server is configured with access to:
  - Your Scrivener projects directory
  - This book-chapter-planner project directory (for writing output)
- Adjust paths if your directories are located elsewhere
- The filesystem server will ONLY have access to directories you specify in the args array

### Verify Zotero Data Directory

Your Zotero data directory should contain:
- `zotero.sqlite` (the main database)
- `storage/` directory (with PDFs and attachments)

If you're unsure of your Zotero data directory location:
1. Open Zotero
2. Go to Preferences > Advanced > Files and Folders
3. Check the "Data Directory Location"

## Restart Claude Desktop

After editing the configuration:
1. Save the `claude_desktop_config.json` file
2. Quit Claude Desktop completely
3. Relaunch Claude Desktop

## Verify Installation

To verify the MCP servers are working:

1. Open Claude Code in your terminal
2. Ask Claude to list available MCP resources:
   ```
   List available MCP servers and resources
   ```

3. You should see:
   - `zotero` server with access to collections and items
   - `filesystem` server with access to specified directories

## Troubleshooting

### Zotero MCP Not Working

**Check that Zotero is not running:**
- The MCP server accesses the database directly
- Zotero locks the database when running
- Close Zotero before using the analysis tool

**Verify the database path:**
```bash
ls -la ~/Zotero/zotero.sqlite
```

### Filesystem MCP Not Working

**Verify permissions:**
- Ensure the directories in the config exist
- Check that you have read permissions

**Test access:**
```bash
ls -la "/Users/anthonytownsend/Dropbox/Apps/Scrivener/FIREWALL.scriv"
```

### General MCP Issues

**Check Claude logs:**
- macOS: `~/Library/Logs/Claude/`
- Look for MCP-related errors

**Verify npx is available:**
```bash
npx --version
```

**Clear npx cache if needed:**
```bash
npx clear-npx-cache
```

## Next Steps

Once MCP servers are configured and verified:
1. Read the main [README.md](README.md) for usage instructions
2. Run your first chapter analysis
3. Review the generated markdown output

## Advanced Configuration

### Multiple Scrivener Projects

If you have multiple book projects, you can add additional paths to the filesystem server:

```json
"args": [
  "-y",
  "@modelcontextprotocol/server-filesystem",
  "/path/to/project1.scriv",
  "/path/to/project2.scriv",
  "/Users/anthonytownsend/code/_dev/book-chapter-planner"
]
```

### Zotero Sync Issues

If you use Zotero sync and have multiple machines:
- Ensure you're pointing to the correct local database
- The MCP server reads from your local database only
- Sync status doesn't affect the analysis tool

## Security Notes

- MCP servers have access only to specified directories
- Your Zotero database is read-only for the MCP server
- No data is sent outside your local machine
- All analysis happens locally with Claude
