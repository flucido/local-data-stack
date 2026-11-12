"""
Entry points for pip-installable CLI commands.

Usage after pip install:
    export-to-rill                    # Export all views
    export-to-rill --view chronic     # Export specific view
    export-to-rill --dry-run          # Preview
"""

import importlib
import importlib.util
import sys
from pathlib import Path


def export_to_rill() -> None:
    """Export DuckDB analytics views to Parquet for Rill dashboards."""
    _run_script("export_to_rill")


def _run_script(name: str) -> None:
    """Import and run a script from the installed `scripts` package or repo path."""
    try:
        module = importlib.import_module(f"scripts.{name}")
        module.main()
        return
    except ModuleNotFoundError:
        pass

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
