# Local-First Archival Second-Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Archive the remaining legacy runtime surfaces so the active repository shape reflects only the local-first `dlt -> DuckDB/dbt -> Parquet export -> Rill` workflow.

**Architecture:** Move remaining non-local-first workflow, monitoring, Docker, and template/package surfaces into new `archive/` buckets as whole units. Then clean active references in docs and config so the active tree no longer presents those archived surfaces as supported.

**Tech Stack:** Git moves, Markdown docs, GitHub Actions YAML, Python project config

---

### Task 1: Create Second-Pass Archive Buckets

**Files:**
- Create: `archive/ci/.gitkeep`
- Create: `archive/monitoring/.gitkeep`
- Create: `archive/docker-stack/.gitkeep`
- Create: `archive/templates/.gitkeep`

- [ ] **Step 1: Create the second-pass archive directories**

Run:

```bash
mkdir -p archive/ci archive/monitoring archive/docker-stack archive/templates
touch archive/ci/.gitkeep archive/monitoring/.gitkeep archive/docker-stack/.gitkeep archive/templates/.gitkeep
```

Expected: all four archive buckets exist.

- [ ] **Step 2: Verify the archive buckets exist**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
for path in [
    'archive/ci/.gitkeep',
    'archive/monitoring/.gitkeep',
    'archive/docker-stack/.gitkeep',
    'archive/templates/.gitkeep',
]:
    assert Path(path).exists(), path
print('second-pass-archive-buckets-ok')
PY
```

Expected output: `second-pass-archive-buckets-ok`

### Task 2: Archive Remaining Legacy Workflow And Runtime Directories

**Files:**
- Modify via move: `.github/workflows/build-push.yml -> archive/ci/build-push.yml`
- Modify via move: `oss_framework/monitoring/ -> archive/monitoring/oss_framework-monitoring/`
- Modify via move: `oss_framework/docker/ -> archive/docker-stack/oss_framework-docker/`
- Modify via move: `oss_framework/pipeline_templates/ -> archive/templates/pipeline_templates/`
- Modify via move: `oss_framework/package_templates/ -> archive/templates/package_templates/`

- [ ] **Step 1: Move the remaining legacy workflow and runtime directories into `archive/`**

Run:

```bash
mv .github/workflows/build-push.yml archive/ci/build-push.yml && mv oss_framework/monitoring archive/monitoring/oss_framework-monitoring && mv oss_framework/docker archive/docker-stack/oss_framework-docker && mv oss_framework/pipeline_templates archive/templates/pipeline_templates && mv oss_framework/package_templates archive/templates/package_templates
```

Expected: the active tree no longer contains those original paths.

- [ ] **Step 2: Verify the moved targets exist and the active originals are gone**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
destinations = [
    'archive/ci/build-push.yml',
    'archive/monitoring/oss_framework-monitoring',
    'archive/docker-stack/oss_framework-docker',
    'archive/templates/pipeline_templates',
    'archive/templates/package_templates',
]
removed = [
    '.github/workflows/build-push.yml',
    'oss_framework/monitoring',
    'oss_framework/docker',
    'oss_framework/pipeline_templates',
    'oss_framework/package_templates',
]
for path in destinations:
    assert Path(path).exists(), path
for path in removed:
    assert not Path(path).exists(), path
print('second-pass-moves-ok')
PY
```

Expected output: `second-pass-moves-ok`

### Task 3: Clean Active GitHub Metadata And CI References

**Files:**
- Modify: `.github/WORKFLOWS.md`
- Modify: `.github/CODEOWNERS`
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: Update `.github/WORKFLOWS.md` to describe only the active workflow surface**

Use `apply_patch` to make these exact changes:

1. Remove references to `build-push.yml` if it has been archived.
2. Keep the document focused on `test.yml` and currently active GitHub metadata only.
3. Remove examples that tell users to run archived workflows.

- [ ] **Step 2: Update `.github/CODEOWNERS` so it covers only active paths**

Use `apply_patch` to remove any ownership entries that point at archived runtime surfaces if any remain after the second-pass moves.

- [ ] **Step 3: Update `.github/workflows/test.yml` path filters to include the active local-first surface and exclude reliance on archived workflow files**

Use `apply_patch` so the workflow watches these active areas:

```yaml
paths:
  - 'oss_framework/**'
  - 'rill_project/**'
  - 'scripts/**'
  - 'schema/**'
  - 'docker-compose.yml'
  - 'pyproject.toml'
  - '.github/workflows/test.yml'
```

Make the same list apply to both `push` and `pull_request`.

- [ ] **Step 4: Verify GitHub metadata no longer presents archived workflows as active**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
workflows_doc = Path('.github/WORKFLOWS.md').read_text()
codeowners = Path('.github/CODEOWNERS').read_text()
test_workflow = Path('.github/workflows/test.yml').read_text()
assert 'build-push.yml' not in workflows_doc
assert 'gh workflow run build-push.yml' not in workflows_doc
assert '.github/workflows/build-push.yml' not in codeowners
assert "scripts/**" in test_workflow and "schema/**" in test_workflow
print('github-metadata-clean-ok')
PY
```

Expected output: `github-metadata-clean-ok`

### Task 4: Clean Contributor And Root Active-Surface Docs

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Update `README.md` if it still implies archived surfaces remain active**

Use `apply_patch` to keep the README aligned with the now-smaller active surface. Remove any wording that still implies monitoring, Docker stack, pipeline templates, or package templates are active first-class areas.

- [ ] **Step 2: Rewrite the active setup, testing, and linting commands in `CONTRIBUTING.md`**

Use `apply_patch` so the contributor guide reflects the active local-first repo shape.

Required command examples:

```bash
git clone https://github.com/YOUR_USERNAME/local-data-stack.git
cd local-data-stack
python -m venv venv
source venv/bin/activate
pip install -e '.[dev]'
python -m pytest oss_framework/tests/
black --check oss_framework
ruff check oss_framework
```

Also remove references to:

- `local-data-stack/oss_framework`
- `pytest tests/`
- `black src/`
- `flake8 src/`
- `pylint src/`
- `pytest --cov=src tests/`

- [ ] **Step 3: Verify contributor and root docs no longer point at archived surfaces as active defaults**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
readme = Path('README.md').read_text()
contrib = Path('CONTRIBUTING.md').read_text()
for banned in [
    'local-data-stack/oss_framework',
    'pytest tests/',
    'black src/',
    'flake8 src/',
    'pylint src/',
    'pytest --cov=src tests/',
]:
    assert banned not in contrib, banned
assert 'pipeline_templates/' not in readme
assert 'package_templates/' not in readme
print('root-and-contrib-docs-clean-ok')
PY
```

Expected output: `root-and-contrib-docs-clean-ok`

### Task 5: Clean Active `oss_framework` Docs After Directory Archival

**Files:**
- Modify: `oss_framework/scripts/README.md`
- Modify: `oss_framework/PRODUCTION_DEPLOYMENT.md`

- [ ] **Step 1: Remove or rewrite references in `oss_framework/scripts/README.md` that still present archived BI/dashboard/runtime surfaces as active**

Use `apply_patch` to remove or rewrite stale guidance such as starting Metabase or other archived runtime tools, while preserving any local-first script guidance that remains relevant.

- [ ] **Step 2: Remove dead or misleading archived-runtime references in `oss_framework/PRODUCTION_DEPLOYMENT.md`**

Use `apply_patch` to ensure the active deployment doc no longer points to missing docs or archived runtime surfaces as if they were current. Archived references are allowed only if clearly labeled as archived reference material.

- [ ] **Step 3: Verify the active `oss_framework` docs no longer present archived runtime surfaces as supported**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
scripts_readme = Path('oss_framework/scripts/README.md').read_text()
prod = Path('oss_framework/PRODUCTION_DEPLOYMENT.md').read_text()
assert 'Metabase' not in scripts_readme
assert 'docs/ARCHITECTURE.md' not in prod
assert 'docs/SETUP.md' not in prod
print('oss-framework-active-docs-clean-ok')
PY
```

Expected output: `oss-framework-active-docs-clean-ok`

### Task 6: Re-Check Packaging After Archival

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove obviously stale runtime contract references from `pyproject.toml` if they are now incorrect after the archive moves**

Use `apply_patch` to update `pyproject.toml` only if the archived moves make active package metadata or defaults obviously wrong.

At minimum, re-check:

- package discovery
- coverage sources
- Ruff first-party config

Do not remove dependencies here unless they are unambiguously outside the supported active contract and the file currently misstates the active package layout.

- [ ] **Step 2: Verify packaging metadata matches the archived repo shape**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path('pyproject.toml').read_text()
assert 'include = ["oss_framework*"]' in text
assert 'source = ["oss_framework"]' in text
assert 'known-first-party = ["oss_framework"]' in text
print('pyproject-second-pass-ok')
PY
```

Expected output: `pyproject-second-pass-ok`

### Task 7: Final Stale-Reference Sweep And Diff Verification

**Files:**
- Modify: none

- [ ] **Step 1: Search the active surface for stale references to second-pass archived paths**

Run:

```bash
rg -n "build-push\.yml|oss_framework/monitoring|oss_framework/docker/|oss_framework/pipeline_templates|oss_framework/package_templates" README.md .github oss_framework scripts rill_project CONTRIBUTING.md
```

Expected: no matches, except explicitly labeled archived/reference-only mentions that are clearly intentional.

- [ ] **Step 2: Verify final git status matches the intended second-pass scope**

Run:

```bash
git status --short
```

Expected: changes are limited to the second-pass archive moves plus the planned active-reference cleanup files.

- [ ] **Step 3: Perform targeted final verification**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
workflow = Path('.github/workflows/test.yml').read_text()
contrib = Path('CONTRIBUTING.md').read_text()
readme = Path('README.md').read_text()
assert 'scripts/**' in workflow and 'schema/**' in workflow
for banned in ['local-data-stack/oss_framework', 'pytest tests/', 'black src/', 'flake8 src/', 'pylint src/', 'pytest --cov=src tests/']:
    assert banned not in contrib, banned
assert 'package_templates/' not in readme
assert 'pipeline_templates/' not in readme
print('second-pass-final-verification-ok')
PY
```

Expected output: `second-pass-final-verification-ok`

## Self-Review

Spec coverage check:

- New archive buckets: covered by Task 1.
- Whole-surface archival of remaining legacy workflow/directories: covered by Task 2.
- Active reference cleanup in docs and config: covered by Tasks 3, 4, 5, and 6.
- Final stale-reference sweep and diff check: covered by Task 7.

Placeholder scan:

- No `TODO`, `TBD`, or deferred implementation notes remain.
- All move, edit, and verification steps have exact paths and commands.

Consistency check:

- Archive destinations match the approved second-pass spec.
- The active surface remains centered on the local-first runtime only.
