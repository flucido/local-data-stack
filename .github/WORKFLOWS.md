# CI/CD Pipeline Guide - GitHub Actions

## Overview

Automated testing, building, and deployment workflows using GitHub Actions.

## Workflows

### 1. Test & Lint (`test.yml`)

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Changes to `oss_framework/` directory

**Jobs**:
- **test** - Runs on Python 3.9, 3.10, 3.11
  - Linting with flake8
  - Format checking with black
  - Unit tests with pytest
  - Coverage reporting to Codecov
  - PostgreSQL integration tests

**Duration**: ~15-20 minutes

**Status Badge**:
```markdown
[![Tests](https://github.com/yourusername/openedDataEstate/actions/workflows/test.yml/badge.svg)](https://github.com/yourusername/openedDataEstate/actions/workflows/test.yml)
```

### 2. Build & Push Docker (`build-push.yml`)

**Triggers**:
- Push to `main` branch
- Tag creation (v*)
- Manual workflow dispatch

**Jobs**:
- **build** - Builds and pushes Docker images
  - Pipeline image (multi-stage)
  - PostgreSQL image
  - Pushes to GitHub Container Registry (GHCR)
  - Tags: `main`, `semantic-version`, `git-sha`, `latest`

**Duration**: ~10-15 minutes

**Image Naming**:
```
ghcr.io/microsoft/openedDataEstate/sis-pipeline:main
ghcr.io/microsoft/openedDataEstate/sis-pipeline:v3.0.0
ghcr.io/microsoft/openedDataEstate/sis-pipeline:main-abc123de
```

### 3. Deploy to Kubernetes (`deploy-k8s.yml`)

**Triggers**:
- Push to `main` branch
- Tag creation (v*)
- Manual workflow dispatch with environment selection

**Jobs**:
- **deploy** - Deploys to Kubernetes cluster
  - Configures kubectl
  - Creates namespace
  - Applies ConfigMaps/Secrets
  - Deploys PostgreSQL StatefulSet
  - Deploys Pipeline Deployment
  - Deploys Dashboards
  - Verifies deployment health
  - Automatic rollback on failure

**Duration**: ~5-10 minutes

**Environments**:
- `dev` (sis-analytics-dev)
- `staging` (sis-analytics-staging)
- `prod` (sis-analytics-prod)

**Secrets Required**:
```
KUBE_CONFIG - base64 encoded kubeconfig
```

## Setup

### 1. Initial Setup

```bash
# Enable GitHub Actions (usually enabled by default)
# Go to repository Settings > Actions > General
```

### 2. Configure Secrets

Go to `Settings > Secrets and variables > Actions`

Add these secrets:

```
KUBE_CONFIG - Your Kubernetes config file (base64 encoded):
  cat ~/.kube/config | base64 -w 0

CODECOV_TOKEN - (Optional) For codecov.io integration
```

### 3. Create Environments

Go to `Settings > Environments`

Create three environments:

- **dev** (no protection)
- **staging** (require approval)
- **prod** (require approval + custom variables)

### 4. Protect Branches

Go to `Settings > Branches > Branch protection rules`

Create rule for `main`:
- ✓ Require status checks to pass before merging
- ✓ Require branches to be up to date
- ✓ Include administrators
- Select status checks:
  - `test (3.9)`
  - `test (3.10)`
  - `test (3.11)`

## Usage

### Automatic Workflows

Workflows run automatically based on triggers:

```bash
git push origin main           # Triggers: test, build-push, deploy
git tag v3.0.0 && git push --tags  # Triggers: build-push, deploy
```

### Manual Workflows

Trigger manually via GitHub UI:

1. Go to `Actions` tab
2. Select workflow
3. Click `Run workflow`
4. Select options (branch, environment)

Or via CLI:

```bash
# Requires GitHub CLI
gh workflow run test.yml -r main
gh workflow run build-push.yml -r main
gh workflow run deploy-k8s.yml -r main -f environment=staging
```

## Monitoring

### View Workflow Runs

```bash
# CLI
gh workflow view

# Web
https://github.com/yourusername/openedDataEstate/actions
```

### View Logs

```bash
# CLI
gh run view <run-id> --log

# Web
Actions > Workflow > Run > Job > Step
```

### Troubleshooting

```bash
# List recent runs
gh run list

# Get detailed run info
gh run view <run-id> --verbose

# Cancel run
gh run cancel <run-id>

# Rerun failed jobs
gh run rerun <run-id> --failed
```

## Workflow Details

### Test Workflow

```yaml
Steps:
1. Checkout code
2. Setup Python + pip cache
3. Install dependencies
4. Lint with flake8 (Python standards)
5. Format check with black (code style)
6. Run pytest tests
7. Upload coverage to Codecov
8. Archive test results
```

Runs on all three Python versions in parallel.

### Build Workflow

```yaml
Steps:
1. Checkout code
2. Setup Docker Buildx
3. Login to GHCR
4. Extract metadata (tags, labels)
5. Build Pipeline image (multi-stage)
6. Push to GHCR (if not PR)
7. Build PostgreSQL image
8. Push to GHCR (if not PR)
```

Uses BuildKit cache for faster builds.

### Deploy Workflow

```yaml
Steps:
1. Checkout code
2. Set environment variables based on target env
3. Setup kubectl
4. Configure kubeconfig from secret
5. Create namespace
6. Apply ConfigMaps and Secrets
7. Deploy PostgreSQL (wait for ready)
8. Deploy Pipeline (wait for ready)
9. Deploy Dashboards (wait for ready)
10. Verify all deployments
11. Post notification
12. Rollback on failure
```

## Best Practices

### 1. Test Locally First

```bash
# Run tests locally before pushing
cd oss_framework
pytest tests/ -v

# Check linting
flake8 oss_framework
black --check oss_framework
```

### 2. Use Semantic Versioning

```bash
# Release new version
git tag v3.0.1
git push origin v3.0.1

# Automatically builds and deploys
```

### 3. Create Protected Branches

- `main` - production-ready (requires PR + tests pass)
- `develop` - development (tests pass)
- Feature branches - work in progress

### 4. Use Environment Approvals

- `prod` - requires approval from maintainers
- `staging` - optional approval
- `dev` - automatic deployment

### 5. Code Review Before Merge

- Require pull request reviews
- Run tests on all PRs
- Block merge if tests fail

## Performance Optimization

### Cache Dependencies

```yaml
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
    cache: 'pip'
```

### Parallel Matrix Builds

```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
```

### Docker BuildKit Cache

```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

## Cost Management

### GitHub Actions Pricing

- Free: 2,000 minutes/month
- Paid: $0.24 per minute extra

### Optimize Usage

- Use matrix strategies efficiently
- Cache dependencies
- Cleanup artifacts
- Use smaller runners for non-critical jobs

## Integration with External Services

### Codecov Integration

```bash
# Coverage upload
- uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

### Slack Notifications

```bash
# Notify on workflow completion
- name: Slack notification
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
```

## Troubleshooting

### Test Failures

```bash
# View detailed logs
gh run view <run-id> --log

# Common issues:
- Missing dependencies: pip install requirements.txt
- PostgreSQL connection: check POSTGRES_HOST env var
- Import errors: check PYTHONPATH
```

### Build Failures

```bash
# Check Docker images
docker images

# Common issues:
- Missing docker credentials: check GITHUB_TOKEN
- Build context: ensure Dockerfile path is correct
- Syntax errors: validate Dockerfile with hadolint
```

### Deploy Failures

```bash
# Check kubectl access
kubectl auth can-i list deployments --namespace=sis-analytics

# Common issues:
- kubeconfig invalid: base64 -d, then verify
- Wrong namespace: check KUBE_NAMESPACE var
- Image not found: check GHCR credentials
```

## Advanced Configuration

### Matrix Strategy

```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
    os: [ubuntu-latest, macos-latest]
  fail-fast: false
```

### Conditional Steps

```yaml
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

### Service Containers

```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_PASSWORD: password
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
```

## Security Best Practices

### Secret Management

- Use GitHub Secrets (not in code)
- Rotate credentials regularly
- Use least privilege access
- Enable secret scanning

### Dependency Security

```bash
# Check for vulnerable dependencies
pip install safety
safety check
```

### Container Scanning

```bash
# Scan Docker images
trivy image ghcr.io/user/repo:latest
```

## Support & Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions Marketplace](https://github.com/marketplace)
- [Workflow Syntax Reference](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
