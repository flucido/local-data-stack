# Local-First Archival Design

## Goal

Reduce the repo to one supported product surface: the local-first analytics workflow built around `dlt -> DuckDB/dbt -> Parquet export -> Rill`.

Everything outside that supported path will remain in the repository for reference, but it will be moved under top-level `archive/` paths and treated as unsupported.

## Supported Architecture

The active, supported workflow is:

1. Stage 1 ingestion from Aeries, Excel, and related local inputs into `oss_framework/data/stage1`
2. DuckDB and dbt transformations in `oss_framework/dbt`
3. Analytics export through `scripts/export_to_rill.py`
4. Dashboard delivery through `rill_project/`

The active surface also includes the minimal project metadata and docs needed to install, run, and verify that workflow.

## Active Surface

These areas remain first-class and should stay in place:

- `README.md`
- `.env.example`
- `pyproject.toml`
- `requirements.txt`
- `uv.lock`
- `docker-compose.yml` after it is corrected to match the local-first layout
- `oss_framework/data/`
- `oss_framework/dbt/`
- `oss_framework/pipelines/`
- active local-first scripts under `oss_framework/scripts/`
- `oss_framework/tests/` that validate the local-first stack
- `scripts/run_pipeline.py`
- `scripts/export_to_rill.py`
- `scripts/contracts/`
- `scripts/metrics_exporter.py` if it still supports the local-first path
- `rill_project/`
- GitHub workflow files that remain relevant to the local-first stack

## Archive Surface

These areas should no longer appear to be supported and will be moved under `archive/`:

- Azure and Synapse setup and sync assets
- legacy Kubernetes deployment assets
- Postgres, Grafana, Superset, pgAdmin, and Prometheus stack assets that describe the old architecture
- stale `src/` code tied to the legacy Delta or DuckLake path
- top-level tests that do not validate the current local-first product
- legacy operational and setup docs that describe older architectures as current

## Archive Layout

Use a top-level `archive/` directory with theme-based subdirectories so the remaining active tree is easy to read.

Planned structure:

- `archive/azure/`
- `archive/k8s/`
- `archive/postgres-stack/`
- `archive/legacy-src/`
- `archive/legacy-tests/`
- `archive/legacy-docs/`

The exact file placement should optimize for clarity over preserving the original folder topology.

## Handling Rules

For this archival pass:

1. Move, do not delete.
2. Do not change the contents of archived files except where a move requires path-safe adjustments such as adding a short archive note file nearby.
3. Remove or disable active references from root docs and active workflows that imply archived material is still supported.
4. Add `archive/README.md` that explains the archive is reference-only and unsupported.
5. Update the root `README.md` to define the line in the sand explicitly and point readers to `archive/` for historical material.

## Workflow and Documentation Changes

The archival pass should include these supporting changes:

1. Update `README.md` so the supported architecture is explicit.
2. Remove active README references that imply `src/`, Azure, Kubernetes, or the Postgres BI stack are part of the main product.
3. Disable or archive workflows that only target archived architectures.
4. Keep the local-first CI path visible and separate from archived delivery paths.

## Non-Goals

This pass does not yet make the repo clean-checkout executable end-to-end. That is the next phase.

This pass also does not repair archived code or make legacy deployments runnable. The point is to reduce ambiguity, not rehabilitate abandoned surfaces.

## Risks

### Risk: accidental archival of still-needed helper code

Mitigation: prefer conservative moves and keep anything that directly supports `run_pipeline.py`, dbt, export, contracts, or Rill in the active tree.

### Risk: stale references after moves

Mitigation: update root docs and active workflow references in the same change.

### Risk: archive becomes a second active surface

Mitigation: add explicit archive documentation and stop linking archived items from active onboarding paths.

## Success Criteria

This archival pass is successful when:

1. A new contributor can identify the supported architecture from the root README without ambiguity.
2. The repo root no longer presents Azure, Kubernetes, Postgres BI, or stale `src/` code as part of the current product.
3. Archived materials are preserved under `archive/` for reference.
4. The remaining active tree cleanly represents the local-first workflow that we intend to harden next.

## Implementation Order

1. Create `archive/` structure and archive notes.
2. Move clearly non-local-first files and directories.
3. Update root docs to define the supported architecture.
4. Disable or archive workflows tied only to archived systems.
5. Run a repo-wide reference check to catch broken active links.

## Open Decisions Resolved

- Archive strategy: move unsupported assets under top-level `archive/`
- Boundary: the only supported architecture is local-first `dlt -> DuckDB/dbt -> Parquet export -> Rill`
- Preservation policy: retain legacy assets for reference, but do not present them as supported
