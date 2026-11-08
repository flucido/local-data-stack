"""dlt pipeline-state isolation.

By default dlt keeps each pipeline's state, schema, and load history in
``~/.dlt/pipelines/<pipeline_name>`` — outside the workspace. That is wrong for
two callers:

* tests and CI, where a warm home directory means a "fresh" pipeline resumes
  from a previous run's state and writes to a different bucket than the one the
  test is inspecting; and
* parallel/sandboxed runs that must not share a destination.

Set ``DLT_PIPELINES_DIR`` to redirect the state directory. Callers read it once
here so every pipeline in the framework resolves the same location.
"""

import os

PIPELINES_DIR_ENV = "DLT_PIPELINES_DIR"


def pipelines_dir() -> str | None:
    """Return the configured dlt pipelines directory, or None for dlt's default."""
    return os.getenv(PIPELINES_DIR_ENV) or None


def pipeline_kwargs() -> dict[str, str]:
    """dlt.pipeline() kwargs that pin the state dir when DLT_PIPELINES_DIR is set.

    Spread into ``dlt.pipeline(...)``; an empty dict leaves dlt's default in place.
    """
    configured = pipelines_dir()
    return {"pipelines_dir": configured} if configured else {}
