# GitHub Actions Workflows

## Active workflow

### Test & Lint (`test.yml`)

This repository currently has one active GitHub Actions workflow: `test.yml`.

**Triggers**
- Push to `main` or `develop` when changes touch `oss_framework/`, `rill_project/`, `scripts/`, `schema/`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.env.example`, `.gitignore`, `docker-compose.yml`, `pyproject.toml`, `requirements.txt`, `uv.lock`, `.github/workflows/test.yml`, `.github/scripts/**`, `.github/CODEOWNERS`, `.github/WORKFLOWS.md`, or `.github/rulesets/**`
- Pull requests to `main` or `develop` with the same path filter

**Jobs**
- `contract-tests` on Python 3.11 for `scripts/contracts/contract_tests.py`
- `test` matrix on Python 3.9, 3.10, and 3.11 after `contract-tests`
- Linting with `ruff`
- Format checking with `black`
- Tests with `pytest`
- Coverage upload to Codecov
- Coverage artifact upload via `actions/upload-artifact`

**Secret**

- Optional secret for coverage upload: `CODECOV_TOKEN`

## Running and monitoring

`test.yml` runs automatically from its configured push and pull request path filters. Manual dispatch is not enabled.

```bash
gh workflow view test.yml
gh run list
gh run view <run-id> --log
```
