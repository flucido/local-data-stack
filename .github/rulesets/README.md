# Branch Protection Rulesets

This directory contains GitHub Repository Ruleset configurations for the `local-data-stack` repository.

## Overview

These rulesets enforce strict branch protection to ensure all code changes are reviewed and vetted before being merged. The configuration follows a "strict by default" philosophy — no one, including repository administrators, can bypass these rules.

## Rulesets

### 1. `main-branch-protection.json` — Main Branch Protection

**Scope**: `main` branch only

**Rules enforced**:

| Rule | Description |
|------|-------------|
| **No deletion** | The `main` branch cannot be deleted |
| **No force pushes** | Force pushes to `main` are blocked |
| **No direct pushes** | Direct pushes to `main` are blocked; all changes must go through a pull request |
| **Require signed commits** | All commits must be cryptographically signed |
| **Pull request required** | All changes must be submitted via pull request with the following requirements: |
| — 1 approving review | At least one approving review is required |
| — Code owner review | Approval from a code owner (defined in `CODEOWNERS`) is required |
| — Dismiss stale reviews | Approvals are dismissed when new commits are pushed |
| — Last push approval | The most recent push must be approved (prevents sneaking in changes after approval) |
| — Resolve conversations | All review conversations must be resolved before merging |
| **Required status checks** | All CI checks must pass before merging: |
| — `contract-tests` | Dashboard contract tests must pass |
| — `test (3.9)` | Python 3.9 test suite must pass |
| — `test (3.10)` | Python 3.10 test suite must pass |
| — `test (3.11)` | Python 3.11 test suite must pass |
| — Strict policy | Branch must be up-to-date with `main` before merging |
| **Linear history** | Only squash or rebase merges allowed (no merge commits) |

**Bypass actors**: None — even repository administrators must follow these rules.

### 2. `all-branches-protection.json` — All Branches Protection

**Scope**: All branches in the repository

**Rules enforced**:

| Rule | Description |
|------|-------------|
| **No deletion** | No branches can be deleted (prevents accidental loss of work) |
| **No force pushes** | Force pushes are blocked on all branches |
| **Require signed commits** | All commits must be cryptographically signed |

**Bypass actors**: None.

## How to Apply

### Option 1: Using the provided script

```bash
# Set your GitHub personal access token (requires repo admin permissions)
export GITHUB_TOKEN="ghp_your_token_here"

# Apply all rulesets
.github/scripts/apply-rulesets.sh
```

### Option 2: Using GitHub CLI

```bash
# Apply main branch protection ruleset
gh api repos/flucido/local-data-stack/rulesets \
  --method POST \
  --input .github/rulesets/main-branch-protection.json

# Apply all branches protection ruleset
gh api repos/flucido/local-data-stack/rulesets \
  --method POST \
  --input .github/rulesets/all-branches-protection.json
```

### Option 3: Using GitHub UI

1. Go to **Settings** → **Rules** → **Rulesets**
2. Click **New ruleset** → **New branch ruleset**
3. Configure each setting to match the JSON configuration

### Option 4: Using the GitHub REST API directly

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/flucido/local-data-stack/rulesets \
  -d @.github/rulesets/main-branch-protection.json
```

## Prerequisites

### Signed Commits

Since signed commits are required, all contributors must set up GPG or SSH signing:

```bash
# GPG signing
git config --global commit.gpgsign true
git config --global user.signingkey YOUR_GPG_KEY_ID

# SSH signing (Git 2.34+)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

See [GitHub's guide on signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

### Code Owners

The `CODEOWNERS` file at `.github/CODEOWNERS` defines @flucido as the required reviewer for all files. This works with the "require code owner review" rule to ensure the repository owner approves all changes.

## Modifying Rulesets

To update an existing ruleset:

1. Edit the JSON file in this directory
2. Find the existing ruleset ID:
   ```bash
   gh api repos/flucido/local-data-stack/rulesets --jq '.[].id'
   ```
3. Update the ruleset:
   ```bash
   gh api repos/flucido/local-data-stack/rulesets/RULESET_ID \
     --method PUT \
     --input .github/rulesets/main-branch-protection.json
   ```

## Removing Rulesets

```bash
# List rulesets with IDs
gh api repos/flucido/local-data-stack/rulesets --jq '.[] | "\(.id) \(.name)"'

# Delete a specific ruleset
gh api repos/flucido/local-data-stack/rulesets/RULESET_ID --method DELETE
```
