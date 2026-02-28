# Intelephense Watcher

Watch PHP files and display Intelephense LSP diagnostics in real-time.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js with Intelephense installed globally: `npm install -g intelephense`

## Installation

```batch
install.bat
```

## Usage

Watch a folder for PHP diagnostics:

```batch
start.bat path\to\php\project
```

Filter by severity level:

```batch
start.bat . --min-severity error
start.bat . --min-severity warning
start.bat . -s info
```

Severity levels (from most to least severe):
- `error` - Only show errors
- `warning` - Errors and warnings
- `info` - Errors, warnings, and info
- `hint` - All diagnostics (default)

Run for a specific duration and exit:

```batch
start.bat . --timeout 10
start.bat . -t 5
```

Write diagnostics to a file:

```batch
start.bat . --output errors.txt
start.bat . -t 10 -o errors.txt
```

Combine options:

```batch
start.bat . -t 5 -s error -o errors.txt
```

Check diagnostics for a single file (indexes full project for cross-file analysis):

```batch
check.bat src/MyClass.php
check.bat src/MyClass.php path\to\project

# Or directly:
start.bat . --file src/MyClass.php
start.bat . -f src/MyClass.php

# Combine with output file:
start.bat . -f src/MyClass.php -o errors.txt
```

Note: The entire project is indexed so missing functions/classes from other files are detected.

Find all references to a symbol at a specific position:

```batch
references.bat src/MyClass.php 10 15
references.bat src/MyClass.php 10 15 path\to\project

# Or directly:
start.bat . --references src/MyClass.php 10 15
start.bat . -r src/MyClass.php 10 15
```

Note: Line and column numbers are **0-indexed** (first line = 0, first column = 0).
Output shows 1-indexed positions for human readability:

```
D:\project\src\MyClass.php:11:16
D:\project\src\OtherClass.php:26:9
```

Go to definition of a symbol at a specific position:

```batch
definition.bat src/MyClass.php 10 15
definition.bat src/MyClass.php 10 15 path\to\project

# Or directly:
start.bat . --definition src/MyClass.php 10 15
start.bat . -d src/MyClass.php 10 15
```

Get hover information (documentation/type) for a symbol:

```batch
hover.bat src/MyClass.php 10 15
hover.bat src/MyClass.php 10 15 path\to\project

# Or directly:
start.bat . --hover src/MyClass.php 10 15
start.bat . -h src/MyClass.php 10 15
```

List all symbols in a file:

```batch
symbols.bat src/MyClass.php
symbols.bat src/MyClass.php path\to\project

# Or directly:
start.bat . --symbols src/MyClass.php
```

Search for symbols across the workspace:

```batch
search.bat MyClass
search.bat MyClass path\to\project

# Or directly:
start.bat . --search MyClass
```

Display server capabilities:

```batch
capabilities.bat path\to\project
start.bat . --capabilities
```

## Development

Run tests:

```batch
tools\tests.bat
```

Update dependencies:

```batch
update.bat
```

## Configuration

### Ignoring Files and Folders

Create an `intelephense.json` file in your project root to ignore specific files or folders from diagnostics:

```json
{
  "ignore": [
    "vendor/**",
    "tests/fixtures/**",
    "*.generated.php"
  ]
}
```

See [HOW_TO_IGNORE_FILES_AND_FOLDERS.md](HOW_TO_IGNORE_FILES_AND_FOLDERS.md) for detailed documentation.

### Underscore-Prefixed Symbols

By default, unused symbols prefixed with underscore are automatically ignored:

- Variables: `$_unused`, `$_response`
- Methods: `_privateHelper()`, `_createTestData()`
- Functions: `_helperFunc()`

This convention indicates "intentionally unused" symbols. Use `--no-ignore-unused-underscore` to show them:

```batch
start.bat . --no-ignore-unused-underscore
```

## Environment Variables

- `DEBUG` - Set to `1` or `true` for debug mode
- `LSP_TIMEOUT` - Request timeout in seconds (default: 30)
- `INTELEPHENSE_HTTP_PORT` - HTTP diagnostics server port (default: 19850)
