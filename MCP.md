# Intelephense MCP Server

This package includes an MCP (Model Context Protocol) server that allows Claude Code to get PHP diagnostics and find references using Intelephense.

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_diagnostics` | Get PHP errors/warnings for a project or specific file | `project_path`, `file_path?`, `min_severity?` |
| `find_references` | Find all references to a symbol at a position | `project_path`, `file_path`, `line`, `column` |
| `get_capabilities` | Get LSP server capabilities | `project_path` |
| `go_to_definition` | Go to symbol definition | `project_path`, `file_path`, `line`, `column` |
| `get_hover` | Get symbol documentation/type | `project_path`, `file_path`, `line`, `column` |
| `get_document_symbols` | List all symbols in file | `project_path`, `file_path` |
| `search_symbols` | Search workspace symbols | `project_path`, `query` |

### Tool Details

#### get_diagnostics
- `project_path` (required): Absolute path to the PHP project root
- `file_path` (optional): Specific file to check (returns all if omitted)
- `min_severity` (optional): Minimum severity level - `error`, `warning`, `info`, `hint` (default: `hint`)

#### find_references
- `project_path` (required): Absolute path to the PHP project root
- `file_path` (required): Absolute path to the PHP file
- `line` (required): 0-indexed line number
- `column` (required): 0-indexed column number

#### get_capabilities
- `project_path` (required): Absolute path to the PHP project root

#### go_to_definition
- `project_path` (required): Absolute path to the PHP project root
- `file_path` (required): Absolute path to the PHP file
- `line` (required): 0-indexed line number
- `column` (required): 0-indexed column number

#### get_hover
- `project_path` (required): Absolute path to the PHP project root
- `file_path` (required): Absolute path to the PHP file
- `line` (required): 0-indexed line number
- `column` (required): 0-indexed column number

#### get_document_symbols
- `project_path` (required): Absolute path to the PHP project root
- `file_path` (required): Absolute path to the PHP file

#### search_symbols
- `project_path` (required): Absolute path to the PHP project root
- `query` (required): Search query (partial name match)

## Registration with Claude Code

### Option 1: Direct registration (recommended)

```bash
claude mcp add --transport stdio intelephense -- uv --directory D:\GIT\BenjaminKobjolke\intelephense-test\intelephense-watcher run python -m intelephense_watcher.mcp_server
```

### Option 2: Using the batch file (Windows)

```bash
claude mcp add --transport stdio intelephense -- cmd /c D:\GIT\BenjaminKobjolke\intelephense-test\intelephense-watcher\mcp-server.bat
```

## Verification

1. **Check MCP status in Claude Code:**
   ```
   /mcp
   ```

2. **Test the tools by asking Claude:**
   - "Use the intelephense tool to check diagnostics for D:\wamp64\www\my-php-project"
   - "Find references to the symbol at line 10, column 5 in src/Controller.php"

## Running Standalone

To test the MCP server standalone:

```bash
cd intelephense-watcher
uv run python -m intelephense_watcher.mcp_server
```

The server will start and wait for JSON-RPC messages on stdin. No output to stdout means it's working correctly (MCP uses stdio for communication).

## Logging

The MCP server logs all activity to `mcp.log` in the project root directory. This includes:
- Server startup events
- Tool calls with their parameters
- LSP client creation and indexing
- Errors and exceptions

**View the log in real-time:**
```bash
# Windows PowerShell
Get-Content -Path "D:\GIT\BenjaminKobjolke\intelephense-test\intelephense-watcher\mcp.log" -Wait

# Windows Command Prompt
type "D:\GIT\BenjaminKobjolke\intelephense-test\intelephense-watcher\mcp.log"
```

**Example log output:**
```
2024-01-15 10:30:00,123 - INFO - ============================================================
2024-01-15 10:30:00,124 - INFO - MCP SERVER STARTING
2024-01-15 10:30:00,125 - INFO - Log file: D:\...\intelephense-watcher\mcp.log
2024-01-15 10:30:00,126 - INFO - Process ID: 12345
2024-01-15 10:30:00,127 - INFO - Waiting for Claude Code connection...
2024-01-15 10:30:05,500 - INFO - TOOL CALL: get_diagnostics(project_path='D:\\wamp64\\www\\my-project', file_path=None, min_severity='hint')
2024-01-15 10:30:05,501 - INFO - Creating new LSP client for: D:\wamp64\www\my-project
2024-01-15 10:30:06,200 - INFO - Indexing 150 PHP files...
2024-01-15 10:30:08,500 - INFO - LSP client ready
```

## Architecture

- **Persistent LSP clients**: The server keeps LSP clients running between calls for faster responses
- **First call latency**: Initial call takes 2-3s for LSP startup + indexing, subsequent calls are instant
- **Memory**: Each project keeps an LSP process running (~50-100MB)
- **Logging**: All activity logged to `mcp.log`, only warnings/errors go to stderr

## Requirements

- Python 3.10+
- Node.js with Intelephense installed globally: `npm install -g intelephense`
- uv package manager
