# How to Integrate Intelephense MCP into Your PHP Project

This guide explains how to set up the Intelephense MCP server for use with Claude Code in your PHP projects.

## Prerequisites

- **Python 3.10+**
- **Node.js** with Intelephense installed globally:
  ```bash
  npm install -g intelephense
  ```
- **uv** package manager (Python)
- **Claude Code** CLI installed

## Step 1: Register the MCP Server with Claude Code

Run one of these commands (only needed once, applies globally):

### Option A: Direct registration (recommended)

```bash
claude mcp add --transport stdio intelephense -- uv --directory D:\GIT\BenjaminKobjolke\intelephense-mpc-windows run python -m intelephense_watcher.mcp_server
```

### Option B: Using the batch file (Windows)

```bash
claude mcp add --transport stdio intelephense -- cmd /c D:\GIT\BenjaminKobjolke\intelephense-mpc-windows\mcp-server.bat
```

## Step 2: Verify Installation

1. Start Claude Code in your project
2. Run `/mcp` to check the server is connected
3. Test with: "Use intelephense to check diagnostics for this project"

## Step 3: Update Your Project's CLAUDE.md

Add the following section to your project's `CLAUDE.md` file to instruct Claude to prefer LSP tools over file search:

```markdown
## LSP Server - MANDATORY

**CRITICAL: ALWAYS use LSP Server FIRST for code navigation tasks.**
**CRITICAL: ALWAYS use LSP Server FIRST for code Search.**
**CRITICAL: ALWAYS use LSP Server understand the code dependency.**

- YOU MUST Proactively suggest fixing LSP diagnostic issues as soon as they appear
- YOU MUST Leave code in a working state after every change
- CRITICAL: ALWAYS publish new LSP diagnostic errors as soon as they appear and suggest fixing them
- CRITICAL: ALWAYS display fixed LSP diagnostic errors in the output after every code change
- CRITICAL: LSP diagnostic errors MUST be displayed as LSP diagnostic in the output after every code change

Before using Search/Glob/Grep/Read to find implementations, references, or definitions:
1. **FIRST try using LSP Server**
2. Only fall back to Search/Glob/Grep if LSP doesn't provide results

### Available MCP Tools (intelephense)

| Tool | Purpose |
|------|---------|
| `mcp__intelephense__find_references` | Find all references to a symbol at position |
| `mcp__intelephense__go_to_definition` | Navigate to symbol definition |
| `mcp__intelephense__get_hover` | Get type info and documentation for symbol |
| `mcp__intelephense__search_symbols` | Search symbols across entire workspace by name |
| `mcp__intelephense__get_document_symbols` | Get all symbols (classes, functions, variables) in a file |
| `mcp__intelephense__get_diagnostics` | Get PHP diagnostics/errors for project or file |
| `mcp__intelephense__reindex` | Force re-index all PHP files (after bulk file operations) |

### Tool Parameters

**All tools require:**
- `project_path`: Absolute path to your project root (e.g., `D:\wamp64\www\my-project`)

**Position-based tools** (find_references, go_to_definition, get_hover):
- `file_path`: Absolute path to PHP file
- `line`: 0-indexed line number
- `column`: 0-indexed column number (position cursor on the symbol name)

**Search tools:**
- `search_symbols`: requires `query` (partial name match)
- `get_document_symbols`: requires `file_path`
- `get_diagnostics`: optional `file_path` (omit for all files), optional `min_severity`
- `reindex`: requires only `project_path` (use after creating/deleting multiple files)

### Usage Examples

```
# Find all references to a method (position on method name)
mcp__intelephense__find_references(project_path, file_path, line=179, column=22)

# Jump to definition from a call site
mcp__intelephense__go_to_definition(project_path, file_path, line=81, column=35)

# Get documentation for a symbol
mcp__intelephense__get_hover(project_path, file_path, line=179, column=22)

# Search for a symbol by name across codebase
mcp__intelephense__search_symbols(project_path, query="MyClassName")

# Get all symbols in a file
mcp__intelephense__get_document_symbols(project_path, file_path)

# Check for PHP errors in project
mcp__intelephense__get_diagnostics(project_path)

# Force re-index after bulk file operations
mcp__intelephense__reindex(project_path)
```

### When to Use LSP (ALWAYS for these tasks)

**MANDATORY - Use LSP Server for:**
- Finding interface implementations (e.g., "what plugins implement this interface?")
- Finding class references (e.g., "where is this class used?")
- Finding method/property usages
- Navigating to definitions
- Getting type information and documentation
- Any code navigation task

**Only use Search/Glob/Grep/Read when:**
- LSP doesn't return results
- Searching for string patterns (not code symbols)
- Searching in non-PHP files
```

## Available Tools Reference

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_diagnostics` | Get PHP errors/warnings for a project or specific file | `project_path`, `file_path?`, `min_severity?` |
| `find_references` | Find all references to a symbol at a position | `project_path`, `file_path`, `line`, `column` |
| `go_to_definition` | Go to symbol definition | `project_path`, `file_path`, `line`, `column` |
| `get_hover` | Get symbol documentation/type | `project_path`, `file_path`, `line`, `column` |
| `get_document_symbols` | List all symbols in file | `project_path`, `file_path` |
| `search_symbols` | Search workspace symbols | `project_path`, `query` |
| `get_capabilities` | Get LSP server capabilities | `project_path` |
| `reindex` | Force re-index all PHP files (new/deleted detection) | `project_path` |

## New File Detection

The MCP server automatically detects newly created PHP files on every `get_diagnostics` call, so references to symbols in new files resolve correctly. For bulk operations (creating/deleting many files at once), use the `reindex` tool to force a complete workspace re-scan.

## Performance Notes

- **First call latency**: Initial call takes 2-3s for LSP startup + indexing
- **Subsequent calls**: Instant (LSP client stays running)
- **Memory**: Each project keeps an LSP process running (~50-100MB)

## Logging

The MCP server logs to `mcp.log` in the intelephense-mpc-windows directory. View in real-time:

```powershell
# PowerShell
Get-Content -Path "D:\GIT\BenjaminKobjolke\intelephense-mpc-windows\mcp.log" -Wait
```

## Troubleshooting

1. **MCP not showing in `/mcp`**: Re-run the registration command
2. **LSP errors**: Ensure `intelephense` is installed globally (`npm install -g intelephense`)
3. **No results**: Check that `project_path` is correct and contains PHP files
4. **Slow first response**: Normal - LSP is indexing the project (2-3s)
