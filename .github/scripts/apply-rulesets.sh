#!/usr/bin/env bash
# apply-rulesets.sh — Apply GitHub repository rulesets via the REST API
#
# Usage:
#   export GITHUB_TOKEN="ghp_your_token_here"
#   .github/scripts/apply-rulesets.sh
#
# Requirements:
#   - A GitHub personal access token with "administration:write" permission
#   - curl and jq installed

set -euo pipefail

OWNER="flucido"
REPO="local-data-stack"
API_BASE="https://api.github.com/repos/${OWNER}/${REPO}/rulesets"
RULESETS_DIR="$(cd "$(dirname "$0")/../rulesets" && pwd)"

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set."
    echo "Please set it with a personal access token that has 'administration:write' permission."
    echo ""
    echo "  export GITHUB_TOKEN=\"ghp_your_token_here\""
    echo "  $0"
    exit 1
fi

apply_ruleset() {
    local file="$1"
    local name
    name=$(jq -r '.name' "$file")

    echo "Applying ruleset: ${name} (from ${file})"

    # Check if a ruleset with this name already exists
    local existing_id
    existing_id=$(curl -s \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "${API_BASE}" | jq -r ".[] | select(.name == \"${name}\") | .id")

    if [ -n "$existing_id" ]; then
        echo "  Updating existing ruleset (ID: ${existing_id})..."
        local response
        response=$(curl -s -w "\n%{http_code}" \
            -X PUT \
            -H "Authorization: Bearer ${GITHUB_TOKEN}" \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "${API_BASE}/${existing_id}" \
            -d @"$file")
    else
        echo "  Creating new ruleset..."
        local response
        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            -H "Authorization: Bearer ${GITHUB_TOKEN}" \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "${API_BASE}" \
            -d @"$file")
    fi

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        local ruleset_id
        ruleset_id=$(echo "$body" | jq -r '.id')
        echo "  Success! Ruleset '${name}' applied (ID: ${ruleset_id})"
    else
        echo "  Error (HTTP ${http_code}):"
        echo "$body" | jq . 2>/dev/null || echo "$body"
        return 1
    fi
}

echo "================================================="
echo "  Applying Branch Protection Rulesets"
echo "  Repository: ${OWNER}/${REPO}"
echo "================================================="
echo ""

errors=0

for ruleset_file in "${RULESETS_DIR}"/*.json; do
    if [ -f "$ruleset_file" ]; then
        if ! apply_ruleset "$ruleset_file"; then
            errors=$((errors + 1))
        fi
        echo ""
    fi
done

echo "================================================="
if [ "$errors" -eq 0 ]; then
    echo "  All rulesets applied successfully!"
else
    echo "  Completed with ${errors} error(s)."
    exit 1
fi
echo "================================================="
