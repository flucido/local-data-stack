"""
Entry points for pip-installable CLI commands.

When the project is installed via pip, these functions are registered
as console_scripts in the user's PATH. They delegate to the existing
scripts that live in the top-level scripts/ directory (which is not
itself a Python package).

Usage after pip install:
    export-to-rill                    # Export all views
    export-to-rill --view chronic     # Export specific view
    export-to-rill --dry-run          # Preview
"""

import importlib.util
import sys
from pathlib import Path


def export_to_rill() -> None:
    """Export DuckDB analytics views to Parquet for Rill dashboards."""
    _run_script("export_to_rill")


def _run_script(name: str) -> None:
    """Import and run a top-level script by file path."""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / f"{name}.py"

    if not script_path.exists():
        print(f"Error: {name} not found at {script_path}", file=sys.stderr)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location(name, script_path)
    if spec is None or spec.loader is None:
        print(f"Error: cannot load {name}", file=sys.stderr)
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
