# Local-First Archival Second-Pass Design

## Goal

Finish the archival boundary by moving the remaining legacy runtime surfaces out of the active tree.

After the first pass, the repo root and primary runtime path are much cleaner, but several directories and workflow assets still present Postgres, Kubernetes, Prometheus, Grafana, Metabase, Superset, or template-driven legacy flows as active surfaces. This second pass removes those remaining mixed signals.

## Supported Surface After This Pass

The supported architecture remains the same:

1. Stage 1 ingestion into `oss_framework/data/stage1`
2. DuckDB and dbt transformations in `oss_framework/dbt`
3. Export through `scripts/export_to_rill.py`
4. Rill dashboards through `rill_project/`

The active repository surface should only include files and directories that directly support that local-first runtime.

## Second-Pass Archive Rule

If a directory or workflow primarily teaches, deploys, monitors, or packages a non-local-first runtime, move the whole surface under `archive/` instead of trying to preserve it as an active but relabeled area.

This pass prefers coarse-grained archival over file-by-file surgery.

## Archive Targets

These remaining active surfaces should move to `archive/` if they still center on the old runtime:

- `.github/workflows/build-push.yml`
- `oss_framework/monitoring/`
- `oss_framework/docker/`
- `oss_framework/pipeline_templates/`
- `oss_framework/package_templates/`

## Proposed Archive Layout

Extend the top-level archive tree with additional themed buckets:

- `archive/ci/`
- `archive/monitoring/`
- `archive/docker-stack/`
- `archive/templates/`

Suggested destination mapping:

- `.github/workflows/build-push.yml` -> `archive/ci/build-push.yml`
- `oss_framework/monitoring/` -> `archive/monitoring/oss_framework-monitoring/`
- `oss_framework/docker/` -> `archive/docker-stack/oss_framework-docker/`
- `oss_framework/pipeline_templates/` -> `archive/templates/pipeline_templates/`
- `oss_framework/package_templates/` -> `archive/templates/package_templates/`

## Active Cleanup Required After The Moves

Once those directories are archived, active references must be cleaned up in the remaining supported surface.

Primary files to re-check and update:

- `README.md`
- `CONTRIBUTING.md`
- `.github/WORKFLOWS.md`
- `.github/CODEOWNERS`
- `.github/workflows/test.yml`
- `pyproject.toml`
- `oss_framework/scripts/README.md`
- `oss_framework/PRODUCTION_DEPLOYMENT.md`

The rule is simple: active docs and config may mention archived assets only when they are explicitly labeled as archived reference material. They must not present those assets as supported or operationally current.

## Non-Goals

This pass does not rehabilitate or modernize the legacy template, monitoring, Docker, or CI surfaces.

This pass also does not yet remove stale dependencies from `pyproject.toml` unless they are clearly part of the now-archived runtime contract and become obviously incorrect after the archive moves.

## Risks

### Risk: over-archiving assets that still help the local-first runtime

Mitigation: only archive directories whose primary purpose is the old runtime. Keep `oss_framework/data`, `dbt`, `pipelines`, active scripts, and active tests in place.

### Risk: broken active documentation links after the move

Mitigation: treat active-reference cleanup as part of the same pass, not a follow-up.

### Risk: hidden active dependencies on archived directories

Mitigation: run a repo-wide reference sweep after the moves and inspect any surviving references before calling the pass complete.

## Success Criteria

This second pass is successful when:

1. No active workflow still builds, deploys, or publishes the legacy Postgres/Kubernetes stack.
2. `oss_framework/monitoring/`, `oss_framework/docker/`, `oss_framework/pipeline_templates/`, and `oss_framework/package_templates/` no longer live on the active surface.
3. Active docs and configuration no longer present the archived runtime as supported.
4. The active repo shape is now clearly and narrowly aligned with the local-first `dlt -> DuckDB/dbt -> Parquet export -> Rill` workflow.

## Implementation Order

1. Create any new archive buckets needed for the second pass.
2. Move the remaining legacy workflow and directory surfaces into `archive/`.
3. Clean active references in docs and config.
4. Re-run the final stale-reference sweep across active paths.
5. Re-check git status so the resulting diff matches the intended second-pass scope.

## Resolved Decisions

- Archive strategy: move entire remaining legacy runtime surfaces, not individual files where avoidable
- Boundary: legacy monitoring, Docker, CI build/push, and template/package surfaces are not part of the supported local-first product
- Archive policy: keep for reference, but remove from the active tree and active support story
