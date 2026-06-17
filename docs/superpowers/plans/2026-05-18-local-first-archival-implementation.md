# Local-First Archival Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the repository to one clearly supported local-first product surface and move legacy architectures into `archive/` without deleting historical material.

**Architecture:** Keep the active local-first runtime in place: `oss_framework` ingestion and dbt assets, root orchestration scripts, and `rill_project`. Move Azure, Kubernetes, Postgres BI stack, stale `src/`, and legacy root tests into themed `archive/` directories. Update active docs and workflows so the remaining root surface matches the supported architecture.

**Tech Stack:** Git moves, Markdown docs, GitHub Actions YAML, Python repo layout, Docker Compose

---

### Task 1: Create Archive Skeleton And Archive Contract

**Files:**
- Create: `archive/README.md`
- Create: `archive/azure/.gitkeep`
- Create: `archive/k8s/.gitkeep`
- Create: `archive/postgres-stack/.gitkeep`
- Create: `archive/legacy-src/.gitkeep`
- Create: `archive/legacy-tests/.gitkeep`
- Create: `archive/legacy-docs/.gitkeep`
- Test: `README.md`

- [ ] **Step 1: Create the archive directory structure**

Run:

```bash
mkdir -p archive/azure archive/k8s archive/postgres-stack archive/legacy-src archive/legacy-tests archive/legacy-docs
touch archive/azure/.gitkeep archive/k8s/.gitkeep archive/postgres-stack/.gitkeep archive/legacy-src/.gitkeep archive/legacy-tests/.gitkeep archive/legacy-docs/.gitkeep
```

Expected: all archive directories exist at repo root.

- [ ] **Step 2: Write `archive/README.md`**

Use `apply_patch` to create this file:

```md
# Archive

This directory contains legacy and unsupported repository material retained for reference only.

## What belongs here

- Azure and Synapse provisioning assets
- legacy Kubernetes deployment assets
- old Postgres, Grafana, Superset, pgAdmin, and Prometheus stack files
- stale source code tied to retired runtime paths
- legacy tests and documentation that do not validate the supported local-first workflow

## Support policy

Nothing under `archive/` is part of the supported product surface.

The supported architecture is the local-first workflow described in the root `README.md`:

`dlt -> DuckDB/dbt -> Parquet export -> Rill`

Files under `archive/` may be historically useful, but they should not be referenced by active onboarding, CI, or deployment paths.
```

- [ ] **Step 3: Verify archive contract is readable**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('archive/README.md').read_text()
assert 'reference only' in text
assert 'not part of the supported product surface' in text
print('archive-readme-ok')
PY
```

Expected output: `archive-readme-ok`

- [ ] **Step 4: Commit archive skeleton**

```bash
git add archive/README.md archive/azure/.gitkeep archive/k8s/.gitkeep archive/postgres-stack/.gitkeep archive/legacy-src/.gitkeep archive/legacy-tests/.gitkeep archive/legacy-docs/.gitkeep
git commit -m "chore: add archive structure for legacy assets"
```

### Task 2: Move Azure, Kubernetes, And Legacy Deployment Assets

**Files:**
- Modify via move: `setup.sh -> archive/azure/setup.sh`
- Modify via move: `.github/workflows/sync.yml -> archive/azure/sync.yml`
- Modify via move: `.github/workflows/deploy-k8s.yml -> archive/k8s/deploy-k8s.yml`
- Modify via move: `k8s-deployment.yaml -> archive/k8s/k8s-deployment.yaml`
- Modify via move: `k8s_deploy.py -> archive/k8s/k8s_deploy.py`
- Modify via move: `oss_framework/k8s-archived/ -> archive/k8s/oss_framework-k8s-archived/`
- Test: `.github/workflows/`

- [ ] **Step 1: Move Azure and Kubernetes assets into `archive/`**

Run:

```bash
mv setup.sh archive/azure/setup.sh && mv .github/workflows/sync.yml archive/azure/sync.yml && mv .github/workflows/deploy-k8s.yml archive/k8s/deploy-k8s.yml && mv k8s-deployment.yaml archive/k8s/k8s-deployment.yaml && mv k8s_deploy.py archive/k8s/k8s_deploy.py && mv oss_framework/k8s-archived archive/k8s/oss_framework-k8s-archived
```

Expected: those files no longer exist in the active root paths.

- [ ] **Step 2: Verify active workflow directory only contains local-first relevant workflows**

Run:

```bash
python - <<'PY'
from pathlib import Path
workflows = sorted(p.name for p in Path('.github/workflows').glob('*.yml'))
print(workflows)
assert 'sync.yml' not in workflows
assert 'deploy-k8s.yml' not in workflows
PY
```

Expected output: workflow list without `sync.yml` and `deploy-k8s.yml`

- [ ] **Step 3: Commit deployment archival move**

```bash
git add archive/azure/setup.sh archive/azure/sync.yml archive/k8s/deploy-k8s.yml archive/k8s/k8s-deployment.yaml archive/k8s/k8s_deploy.py archive/k8s/oss_framework-k8s-archived .github/workflows
git commit -m "chore: archive azure and kubernetes assets"
```

### Task 3: Move Legacy Postgres BI Stack And Operational Docs

**Files:**
- Modify via move: `oss_framework/docker-compose.yml -> archive/postgres-stack/oss_framework-docker-compose.yml`
- Modify via move: `oss_framework/UAT_PLAN.md -> archive/legacy-docs/UAT_PLAN.md`
- Modify via move: `oss_framework/OPERATIONAL_RUNBOOKS.md -> archive/legacy-docs/OPERATIONAL_RUNBOOKS.md`
- Test: `oss_framework/`

- [ ] **Step 1: Move legacy stack and docs**

Run:

```bash
mv oss_framework/docker-compose.yml archive/postgres-stack/oss_framework-docker-compose.yml && mv oss_framework/UAT_PLAN.md archive/legacy-docs/UAT_PLAN.md && mv oss_framework/OPERATIONAL_RUNBOOKS.md archive/legacy-docs/OPERATIONAL_RUNBOOKS.md
```

Expected: `oss_framework/` no longer contains the old Compose file or legacy runbook docs.

- [ ] **Step 2: Verify the active `oss_framework/` surface is focused on the local-first path**

Run:

```bash
python - <<'PY'
from pathlib import Path
assert not Path('oss_framework/docker-compose.yml').exists()
assert not Path('oss_framework/UAT_PLAN.md').exists()
assert not Path('oss_framework/OPERATIONAL_RUNBOOKS.md').exists()
print('oss-framework-legacy-assets-archived')
PY
```

Expected output: `oss-framework-legacy-assets-archived`

- [ ] **Step 3: Commit legacy stack archival**

```bash
git add archive/postgres-stack/oss_framework-docker-compose.yml archive/legacy-docs/UAT_PLAN.md archive/legacy-docs/OPERATIONAL_RUNBOOKS.md oss_framework
git commit -m "chore: archive legacy postgres stack assets"
```

### Task 4: Move Stale Source Tree And Legacy Root Tests

**Files:**
- Modify via move: `src/ -> archive/legacy-src/src/`
- Modify via move: `test_uat.py -> archive/legacy-tests/test_uat.py`
- Modify via move: `test_rill_integration.py -> archive/legacy-tests/test_rill_integration.py`
- Modify via move: `test_performance.py -> archive/legacy-tests/test_performance.py`
- Modify via move: `test_rbac.py -> archive/legacy-tests/test_rbac.py`
- Test: repo root

- [ ] **Step 1: Move stale source and legacy root tests**

Run:

```bash
mv src archive/legacy-src/src && mv test_uat.py archive/legacy-tests/test_uat.py && mv test_rill_integration.py archive/legacy-tests/test_rill_integration.py && mv test_performance.py archive/legacy-tests/test_performance.py && mv test_rbac.py archive/legacy-tests/test_rbac.py
```

Expected: the repo root no longer contains `src/` or the four legacy test files.

- [ ] **Step 2: Verify active root surface no longer advertises stale runtime paths**

Run:

```bash
python - <<'PY'
from pathlib import Path
assert not Path('src').exists()
for name in ['test_uat.py', 'test_rill_integration.py', 'test_performance.py', 'test_rbac.py']:
    assert not Path(name).exists(), name
print('legacy-root-assets-archived')
PY
```

Expected output: `legacy-root-assets-archived`

- [ ] **Step 3: Commit stale source archival**

```bash
git add archive/legacy-src/src archive/legacy-tests/test_uat.py archive/legacy-tests/test_rill_integration.py archive/legacy-tests/test_performance.py archive/legacy-tests/test_rbac.py
git commit -m "chore: archive stale source tree and legacy tests"
```

### Task 5: Rewrite Root README Around The Supported Architecture

**Files:**
- Modify: `README.md`
- Test: `README.md`

- [ ] **Step 1: Update the repository layout section to remove archived paths from the active story**

Use `apply_patch` to revise `README.md` so the layout section describes only the active local-first surface and adds an `archive/` entry marked as unsupported historical material.

Required content changes:

```md
├── archive/                     # Unsupported historical assets kept for reference
├── oss_framework/
│   ├── data/
│   ├── dbt/
│   ├── pipelines/
│   ├── scripts/
│   └── tests/
├── rill_project/
├── scripts/
```

Remove the `src/` entry from the active layout.

- [ ] **Step 2: Update the architecture and quick-start text to reflect Stage 4 export explicitly**

Use `apply_patch` to make these changes in `README.md`:

1. Change the architecture overview so Stage 3 is DuckDB analytics marts and Stage 4 is Parquet export for Rill.
2. Replace the current Rill launch step with a sequence that makes export part of the supported path.
3. Add a short section that states anything not in the local-first runtime is archived under `archive/` and unsupported.

Required command block:

```bash
python scripts/run_pipeline.py --stage all
cd rill_project
rill start
```

- [ ] **Step 3: Verify the README contains the line in the sand**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('README.md').read_text()
assert 'archive/' in text
assert 'unsupported historical assets kept for reference' in text
assert 'python scripts/run_pipeline.py --stage all' in text
assert 'anything outside that local-first runtime is archived' in text.lower()
print('readme-local-first-ok')
PY
```

Expected output: `readme-local-first-ok`

- [ ] **Step 4: Commit README rewrite**

```bash
git add README.md
git commit -m "docs: define local-first architecture as supported surface"
```

### Task 6: Clean Up Active CI And Root Docker Compose References

**Files:**
- Modify: `.github/workflows/test.yml`
- Modify: `docker-compose.yml`
- Test: `.github/workflows/test.yml`
- Test: `docker-compose.yml`

- [ ] **Step 1: Narrow the workflow triggers and test scope to active surfaces**

Use `apply_patch` on `.github/workflows/test.yml` to make these exact changes:

1. Remove `dashboards/**` from push and pull request path filters if it is not present in the active tree.
2. Remove the Postgres service block entirely.
3. Replace the black step with `black --check oss_framework` without `|| true`.
4. Keep the workflow focused on `oss_framework/**`, `rill_project/**`, `scripts/contracts/**`, and the workflow file itself.

- [ ] **Step 2: Correct root Docker Compose to point at the active local-first layout**

Use `apply_patch` on `docker-compose.yml` to make these exact changes:

1. Change the Rill command to `rill start --project /app/rill_project`.
2. Change `STAGE1_PATH`, `STAGE2_PATH`, and `STAGE3_PATH` to `/home/jovyan/work/oss_framework/data/stage1`, `/home/jovyan/work/oss_framework/data/stage2`, and `/home/jovyan/work/oss_framework/data/stage3`.

- [ ] **Step 3: Validate workflow and Compose file text**

Run:

```bash
python - <<'PY'
from pathlib import Path
workflow = Path('.github/workflows/test.yml').read_text()
compose = Path('docker-compose.yml').read_text()
assert 'postgres:' not in workflow
assert '|| true' not in workflow
assert 'rill start --project /app/rill_project' in compose
assert '/home/jovyan/work/oss_framework/data/stage1' in compose
print('workflow-and-compose-ok')
PY
```

Expected output: `workflow-and-compose-ok`

- [ ] **Step 4: Commit active surface cleanup**

```bash
git add .github/workflows/test.yml docker-compose.yml
git commit -m "chore: align active tooling with local-first architecture"
```

### Task 7: Final Reference Check And Repo Verification

**Files:**
- Modify: none
- Test: repository-wide references

- [ ] **Step 1: Search active files for stale references to archived root paths**

Run:

```bash
rg -n "setup\.sh|sync\.yml|deploy-k8s\.yml|k8s-deployment\.yaml|k8s_deploy\.py|oss_framework/docker-compose\.yml|test_uat\.py|test_rbac\.py|test_performance\.py|test_rill_integration\.py|\bsrc/" README.md .github oss_framework scripts rill_project docs
```

Expected: no matches in active files, except intentional mentions inside the archival spec and implementation plan under `docs/superpowers/`.

- [ ] **Step 2: Check git status for only intended archive and cleanup changes**

Run:

```bash
git status --short
```

Expected: only the moved archive paths, docs updates, workflow update, Compose update, and plan/spec files appear.

- [ ] **Step 3: Commit final consistency cleanup if needed**

```bash
git add archive README.md .github/workflows/test.yml docker-compose.yml docs/superpowers/specs/2026-05-18-local-first-archival-design.md docs/superpowers/plans/2026-05-18-local-first-archival-implementation.md
git commit -m "chore: archive non-local-first repository surfaces"
```

## Self-Review

Spec coverage check:

- Archive strategy under top-level `archive/`: covered by Tasks 1 through 4.
- Update root docs to define supported architecture: covered by Task 5.
- Remove active references from workflows and tooling: covered by Task 6.
- Verify active tree no longer presents legacy surfaces as supported: covered by Task 7.

Placeholder scan:

- No `TODO`, `TBD`, or deferred implementation notes remain.
- Every move and verification step has exact commands.

Consistency check:

- Archive directory names match the approved spec.
- Supported architecture wording is consistent with the spec: `dlt -> DuckDB/dbt -> Parquet export -> Rill`.
