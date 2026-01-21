"""Main entry point for Intelephense Watcher CLI."""

import argparse
import json
import os
import sys
import time

from watchdog.observers import Observer

from intelephense_watcher.config.config_file import get_ignore_patterns, load_config_file
from intelephense_watcher.config.constants import COLORS, CONSTANTS
from intelephense_watcher.config.settings import Settings
from intelephense_watcher.diagnostics import DiagnosticsDisplay
from intelephense_watcher.file_handler import PhpFileHandler, scan_php_files
from intelephense_watcher.lsp_client import LspClient
from intelephense_watcher.utils import normalize_uri, path_to_uri, uri_to_path


def _symbol_kind_name(kind: int) -> str:
    """Convert symbol kind number to name."""
    kinds = {
        1: "File", 2: "Module", 3: "Namespace", 4: "Package",
        5: "Class", 6: "Method", 7: "Property", 8: "Field",
        9: "Constructor", 10: "Enum", 11: "Interface", 12: "Function",
        13: "Variable", 14: "Constant", 15: "String", 16: "Number",
        17: "Boolean", 18: "Array", 19: "Object", 20: "Key",
        21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
        25: "Operator", 26: "TypeParameter",
    }
    return kinds.get(kind, f"Kind{kind}")


def _print_symbols(symbols: list, indent: int = 0) -> None:
    """Print document symbols recursively."""
    prefix = "  " * indent
    for sym in symbols:
        name = sym.get("name", "?")
        kind = _symbol_kind_name(sym.get("kind", 0))

        # Get location info
        if "range" in sym:
            start = sym["range"]["start"]
            line_num = start["line"] + 1
            print(f"{prefix}{kind}: {name} (line {line_num})")
        elif "location" in sym:
            start = sym["location"]["range"]["start"]
            line_num = start["line"] + 1
            print(f"{prefix}{kind}: {name} (line {line_num})")
        else:
            print(f"{prefix}{kind}: {name}")

        # Handle children (DocumentSymbol format)
        if "children" in sym:
            _print_symbols(sym["children"], indent + 1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Watch a PHP project folder and display Intelephense diagnostics."
    )
    parser.add_argument("folder_path", help="Path to the PHP project folder to watch")
    parser.add_argument(
        "--min-severity",
        "-s",
        choices=["error", "warning", "info", "hint"],
        default="hint",
        help="Minimum severity level to display (default: hint, shows all)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=None,
        help="Run for N seconds then exit (default: watch forever)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write diagnostics to file instead of console",
    )
    parser.add_argument(
        "--capabilities",
        "-c",
        action="store_true",
        help="Display server capabilities and exit",
    )
    parser.add_argument(
        "--references",
        "-r",
        nargs=3,
        metavar=("FILE", "LINE", "COL"),
        help="Find references at FILE:LINE:COL (0-indexed) and exit",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Check diagnostics for a single file and exit",
    )
    parser.add_argument(
        "--definition",
        "-d",
        nargs=3,
        metavar=("FILE", "LINE", "COL"),
        help="Go to definition at FILE:LINE:COL (0-indexed) and exit",
    )
    parser.add_argument(
        "--hover",
        nargs=3,
        metavar=("FILE", "LINE", "COL"),
        help="Get hover info at FILE:LINE:COL (0-indexed) and exit",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        metavar="FILE",
        help="List all symbols in FILE and exit",
    )
    parser.add_argument(
        "--search",
        type=str,
        metavar="QUERY",
        help="Search for symbols matching QUERY and exit",
    )
    parser.add_argument(
        "--no-ignore-unused-underscore",
        action="store_true",
        help="Show 'unused variable' hints for underscore-prefixed variables (default: hidden)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "csv"],
        default="text",
        help="Output format when using --output (default: text, auto-detects csv from .csv extension)",
    )
    return parser.parse_args()


def _should_use_csv(args: argparse.Namespace) -> bool:
    """Determine if CSV format should be used based on args and output filename.

    Args:
        args: Parsed command-line arguments.

    Returns:
        True if CSV format should be used.
    """
    if args.format == "csv":
        return True
    if args.output and args.output.lower().endswith(".csv"):
        return True
    return False


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()

    folder_path = args.folder_path
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a valid directory")
        sys.exit(1)

    # Load config file
    config = load_config_file(folder_path)
    ignore_patterns = get_ignore_patterns(config)

    # Create settings from CLI args
    settings = Settings(
        workspace_path=folder_path,
        min_severity=CONSTANTS.SEVERITY_NAMES[args.min_severity],
        timeout=args.timeout,
        output_file=args.output,
        ignore_unused_underscore=not args.no_ignore_unused_underscore,
        ignore_patterns=ignore_patterns,
    )

    print(f"{COLORS.CYAN}Starting Intelephense LSP Watcher...{COLORS.RESET}")
    print(f"Workspace: {settings.workspace_path}")

    # Initialize components
    lsp_client = LspClient(settings.workspace_path, request_timeout=settings.request_timeout)
    display = DiagnosticsDisplay(
        settings.workspace_path,
        min_severity=settings.min_severity,
        ignore_unused_underscore=settings.ignore_unused_underscore,
        ignore_patterns=settings.ignore_patterns,
    )

    # Start LSP server
    print("Starting Intelephense...")
    if not lsp_client.start():
        sys.exit(1)

    # Initialize LSP
    print("Initializing LSP connection...")
    if not lsp_client.initialize():
        print(f"{COLORS.RED}Failed to initialize LSP connection{COLORS.RESET}")
        lsp_client.stop()
        sys.exit(1)

    # If --capabilities flag is set, display capabilities and exit
    if args.capabilities:
        print(json.dumps(lsp_client.server_capabilities, indent=2))
        lsp_client.stop()
        sys.exit(0)

    # If --references flag is set, find references and exit
    if args.references:
        file_path, line, col = args.references
        abs_file = os.path.abspath(file_path)

        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for fp in php_files:
            lsp_client.open_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for indexing

        refs = lsp_client.find_references(abs_file, int(line), int(col))
        if refs:
            for ref in refs:
                path = uri_to_path(ref["uri"])
                start = ref["range"]["start"]
                print(f"{path}:{start['line'] + 1}:{start['character'] + 1}")
        else:
            print("No references found")
        lsp_client.stop()
        sys.exit(0)

    # If --definition flag is set, go to definition and exit
    if args.definition:
        file_path, line, col = args.definition
        abs_file = os.path.abspath(file_path)

        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for fp in php_files:
            lsp_client.open_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for indexing

        result = lsp_client.go_to_definition(abs_file, int(line), int(col))
        if result:
            locations = result if isinstance(result, list) else [result]
            for loc in locations:
                path = uri_to_path(loc["uri"])
                start = loc["range"]["start"]
                print(f"{path}:{start['line'] + 1}:{start['character'] + 1}")
        else:
            print("No definition found")
        lsp_client.stop()
        sys.exit(0)

    # If --hover flag is set, get hover info and exit
    if args.hover:
        file_path, line, col = args.hover
        abs_file = os.path.abspath(file_path)

        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for fp in php_files:
            lsp_client.open_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for indexing

        result = lsp_client.get_hover(abs_file, int(line), int(col))
        if result:
            contents = result.get("contents", {})
            if isinstance(contents, dict):
                print(contents.get("value", str(contents)))
            elif isinstance(contents, list):
                for item in contents:
                    if isinstance(item, dict):
                        print(item.get("value", str(item)))
                    else:
                        print(str(item))
            else:
                print(str(contents))
        else:
            print("No hover information available")
        lsp_client.stop()
        sys.exit(0)

    # If --symbols flag is set, list document symbols and exit
    if args.symbols:
        abs_file = os.path.abspath(args.symbols)

        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for fp in php_files:
            lsp_client.open_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for indexing

        result = lsp_client.get_document_symbols(abs_file)
        if result:
            _print_symbols(result)
        else:
            print("No symbols found")
        lsp_client.stop()
        sys.exit(0)

    # If --search flag is set, search workspace symbols and exit
    if args.search:
        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for fp in php_files:
            lsp_client.open_document(fp)

        time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for indexing

        result = lsp_client.search_symbols(args.search)
        if result:
            for sym in result:
                name = sym.get("name", "?")
                kind = _symbol_kind_name(sym.get("kind", 0))
                loc = sym.get("location", {})
                loc_path = uri_to_path(loc.get("uri", ""))
                start = loc.get("range", {}).get("start", {})
                line_num = start.get("line", 0) + 1
                print(f"{kind}: {name} - {loc_path}:{line_num}")
        else:
            print(f"No symbols found matching '{args.search}'")
        lsp_client.stop()
        sys.exit(0)

    # If --file flag is set, check single file diagnostics and exit
    if args.file:
        abs_file = os.path.abspath(args.file)
        if not os.path.isfile(abs_file):
            print(f"Error: '{args.file}' is not a valid file")
            lsp_client.stop()
            sys.exit(1)

        # Scan and open ALL PHP files so LSP has full project context
        php_files = scan_php_files(settings.workspace_path)
        for file_path in php_files:
            lsp_client.open_document(file_path)

        # Use --timeout if provided, otherwise use default delay
        delay = settings.timeout if settings.timeout else CONSTANTS.DIAGNOSTICS_DELAY
        time.sleep(delay)

        # Filter diagnostics to only show the target file
        target_uri = normalize_uri(path_to_uri(abs_file))

        with lsp_client.diagnostics_lock:
            filtered_diagnostics = {
                uri: diags for uri, diags in lsp_client.diagnostics.items()
                if normalize_uri(uri) == target_uri
            }
            if _should_use_csv(args):
                output = display.format_csv(filtered_diagnostics)
                # CSV has header line, so check if there's more than just the header
                has_output = output.count("\n") > 1 or (output.count("\n") == 1 and not output.endswith("\n"))
            else:
                output = display.format_plain(filtered_diagnostics)
                has_output = bool(output.strip())

        if settings.output_file:
            if has_output:
                with open(settings.output_file, "w", encoding="utf-8") as f:
                    f.write(output)
                print(f"Diagnostics written to: {settings.output_file}")
            else:
                print("No diagnostics found, skipping file creation")
        else:
            if output.strip():
                print(output)
            else:
                print("No diagnostics found")

        lsp_client.stop()
        sys.exit(0)

    # Give server a moment to initialize
    time.sleep(CONSTANTS.INIT_DELAY)

    # Scan and open existing PHP files
    print("Scanning for PHP files...")
    php_files = scan_php_files(settings.workspace_path)
    print(f"Found {len(php_files)} PHP file(s)")

    for file_path in php_files:
        lsp_client.open_document(file_path)

    # Set up file watcher
    event_handler = PhpFileHandler(lsp_client, debounce_delay=CONSTANTS.DEBOUNCE_DELAY)
    observer = Observer()
    observer.schedule(event_handler, settings.workspace_path, recursive=True)
    observer.start()

    # Initial display
    time.sleep(CONSTANTS.DIAGNOSTICS_DELAY)  # Wait for initial diagnostics

    if settings.timeout:
        # Timeout mode: wait, then output once and exit
        time.sleep(settings.timeout)
        with lsp_client.diagnostics_lock:
            diagnostics_dict = dict(lsp_client.diagnostics)
            if _should_use_csv(args):
                output = display.format_csv(diagnostics_dict)
                # CSV has header line, so check if there's more than just the header
                has_output = output.count("\n") > 1 or (output.count("\n") == 1 and not output.endswith("\n"))
            else:
                output = display.format_plain(diagnostics_dict)
                has_output = bool(output.strip())
        if settings.output_file:
            if has_output:
                with open(settings.output_file, "w", encoding="utf-8") as f:
                    f.write(output)
                print(f"Diagnostics written to: {settings.output_file}")
            else:
                print("No diagnostics found, skipping file creation")
        else:
            print(output)
        # Clean shutdown
        observer.stop()
        lsp_client.stop()
        observer.join()
    else:
        # Watch mode - set up live diagnostics callback
        def on_diagnostics_updated() -> None:
            with lsp_client.diagnostics_lock:
                display.display(dict(lsp_client.diagnostics))

        lsp_client.on_diagnostics_updated = on_diagnostics_updated
        on_diagnostics_updated()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{COLORS.CYAN}Shutting down...{COLORS.RESET}")
            observer.stop()
            lsp_client.stop()

        observer.join()
        print("Goodbye!")


if __name__ == "__main__":
    main()
