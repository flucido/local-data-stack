---
name: rill-agentic-patterns
description: Agentic development patterns for Rill analytics. Use when building agent-friendly analytics,
  designing metrics layers for AI consumption, wiring MCP tools, creating conversational BI features,
  setting up eval harnesses for analytics agents, or applying context engineering patterns.
  Triggers on "agentic", "agent-friendly", "MCP", "conversational BI", "context engineering",
  "AI agent + analytics", "eval harness", or when designing how AI agents interact with
  the analytics stack.
metadata:
  version: 1.0.0
  sources:
    - https://www.rilldata.com/blog/rill-agentic-architecture-analytics-for-the-ai-era
    - https://www.rilldata.com/blog/building-an-agent-friendly-local-first-analytics-stack-with-motherduck-and-rill
---

# Rill Agentic Development Patterns

You are an expert in building agent-friendly analytics systems using Rill.
These patterns are drawn from Rill's production agentic architecture and the
principles that make a BI stack genuinely usable by AI agents.

## Core Architecture Principle

**One runtime, many clients.** Dashboards, AI agents, and human analysts are
all clients of the same metrics layer — not separate systems that drift apart.

```
Human Analyst ──┐
Dashboard UI  ──┼── Metrics Layer (YAML + SQL) ── OLAP Engine (DuckDB)
AI Agent      ──┘
External MCP  ──┘
```

The metrics layer is the contract. Every client resolves the same measure
from the same governed definition. No copies. No drift.

## Design Constraints for Agent-Friendly Analytics

These are gates — violations should be flagged:

### 1. Declarative, Text-Based Definitions Only

**Rule:** All data models, metrics, and dashboards MUST be defined as
YAML + SQL files in version control. No GUI-only configurations.

**Why:** AI agents read code, not GUIs. A dashboard defined in YAML is
agent-readable. A dashboard built by clicking in a web UI is opaque.

```yaml
# Good: Agent can read, understand, and edit
type: metrics_view
model: student_attendance
measures:
  - name: absence_rate
    expression: SUM(days_absent) * 100.0 / NULLIF(SUM(days_enrolled), 0)
```

```yaml
# Bad: GUI-created, no code artifact, agent cannot reason about it
# (This pattern should not exist in the project)
```

### 2. Single Source of Truth for Business Logic

**Rule:** Every metric MUST be defined exactly once. If "revenue" appears
in two places, one must delegate to the other. Use derived metrics views
(`parent`) or reference measures (`requires`) instead of duplicating.

```yaml
# Good: Derived metrics view inherits from parent
parent: base_revenue_metrics
parent_measures: "*"
```

```
# Bad: Same expression defined independently in multiple files
# File A: revenue = SUM(order_total)
# File B: revenue = SUM(order_total)   <-- DRIFT RISK
```

### 3. Local-First, CLI-Verifiable

**Rule:** Every change MUST be verifiable locally before committing.
Run `rill start` and visually confirm dashboards render correctly.
Run `rill validate` to catch parse errors.

```bash
cd rill_project && rill start       # Verify locally
cd rill_project && rill validate    # Check for errors
```

**Why:** Agentic workflows produce many changes fast. Local verification
is the human-in-the-loop gate preventing bad code from deploying.

### 4. Deterministic Over Probabilistic

**Rule:** Metrics definitions, models, and dashboards MUST be deterministic.
Avoid natural language definitions that agents (or humans) could interpret
differently. Use `ai_instructions` for domain context, not as a substitute
for precise measure expressions.

```yaml
# Good: Precise, deterministic
measures:
  - name: active_students
    expression: COUNT(DISTINCT CASE WHEN status = 'enrolled' THEN student_id END)

# Avoid: Ambiguous natural language as the only definition
# "Count how many active students we have" -- agent must guess
```

### 5. SQL as the Interface Language

**Rule:** Query metrics views using Metrics SQL, not raw table SQL.
This ensures agents work through the governed metrics layer rather
than bypassing it with ad-hoc queries against raw tables.

```sql
-- Good: Metrics SQL through the semantic layer
SELECT school_id, chronic_absence_rate
FROM chronic_absenteeism_risk
ORDER BY chronic_absence_rate DESC

-- Avoid in agent contexts: Raw SQL against underlying tables
-- SELECT school_id, SUM(absent) / COUNT(*) FROM raw_attendance_data GROUP BY 1
```

### 6. Context-Aware Resource Design

**Rule:** Include `description`, `display_name`, and `ai_instructions`
on every metrics view resource. Agents cannot infer business meaning
from column names alone.

```yaml
dimensions:
  - name: risk_level
    display_name: "Risk Level"
    description: "Categorical risk classification: low (<5% absenteeism), moderate (5-10%), high (>10%)"
    column: risk_level

measures:
  - name: chronic_absence_rate
    display_name: "Chronic Absence Rate"
    description: "Percentage of students missing 10%+ of enrolled days in the period"
    expression: ROUND(SUM(chronic_absence_flag) * 100.0 / NULLIF(COUNT(DISTINCT student_key), 0), 1)
```

## Context Engineering Patterns

These patterns improve agent reliability and reduce hallucinations.
Sourced from Rill's production agent system.

### Pattern: Pre-Warm Context

Don't make the agent discover what the codebase already knows.
When an agent is launched from a known context (specific dashboard,
metrics view), preload the relevant schema, data preview, and
project status before the model starts reasoning.

**Implementation:** When working on a specific metrics view,
always inspect it first before making changes:

```
1. Read the existing YAML file
2. Check the model/table schema with rill query (if running)
3. Look at related dashboards for consistency
4. THEN propose changes
```

### Pattern: Bound Everything

**Rule:** All agent-driven operations MUST have explicit bounds:
- Queries: Always specify LIMIT (default 100 if not specified)
- Iterations: Maximum 10 edit-verify cycles before requiring human review
- Output: Paginate results, show next-page information
- Context: Prune irrelevant tool results, compact middle turns

```
# Query constraint for agents
SELECT ... LIMIT 100   # Never let an agent run unbounded queries
```

### Pattern: Citations as Reasoning Constraint

**Rule:** Any claim about data MUST cite the exact query that produced it.
If an agent cannot cite the query, it should re-query. This prevents
hallucinations by forcing the agent to maintain a query-result chain.

```
Claim: "Chronic absenteeism is highest in grade 9 at 23%."
Citation: FROM chronic_absenteeism_risk SELECT grade_level, chronic_absence_rate
          WHERE grade_level = '9' -> returned 0.2345
```

### Pattern: Iteration Cap with Hard Stop

**Rule:** Agent edit loops MUST have a maximum iteration count (10).
On the final iteration, strip tools and force the model to produce
a summary rather than continuing to loop. Treat the cap as a guardrail,
not the happy path.

### Pattern: Compact Context Across Iterations

**Rule:** Preserve the first few messages (project context), the latest
turns (current state), and prune orphaned tool calls from the middle
into a high-signal summary. The goal is preserving facts that affect
the next decision, not every token.

## Agent-Human Collaboration Model

### The Human Role

The human is the domain expert and the verifier. The agent handles
technical translation and code generation. The human reviews the
declarative YAML output.

```
Human  ── "Set up chronic absenteeism dashboard"
Agent  ── Reads model schema, generates metrics_view YAML
Human  ── Reviews YAML, runs rill start, visually confirms
Agent  ── Adjusts based on feedback, regenerates
Human  ── Approves, commits to Git
```

### Code as the Abstraction Layer

Natural language is the input interface, but CODE (YAML + SQL) is
the output artifact. The agent translates "I want to see attendance
by grade level" into precise, deterministic YAML that can be reviewed,
tested, and versioned.

**Never let an agent produce "the answer is 42" without also producing
the code artifact that generated it.**

## MCP & External Agent Integration

### Rill MCP Server

Rill ships an MCP server that exposes metrics views to Claude Code,
Cursor, and other MCP-compatible agents. Internal agents and external
tools use the same handlers and access checks.

**Key principle:** Tools are a contract. The same tools available to
Rill's internal agents are exposed to external agents via MCP.
One place to fix bugs, one place to add capabilities.

### Agent Tools Available

When connected via MCP, agents can:
- List and inspect metrics views
- Inspect data stats and sample values
- Run Metrics SQL queries
- Create chart components (Vega specs)
- Open and navigate to dashboards

### Adding ai_instructions for Agent Guidance

```yaml
# Project-level (rill.yaml)
ai_instructions: |
  This project tracks K-12 education analytics.
  All attendance rates use a 180-day school year as baseline.
  Special education status should always be filterable.

# Resource-level (metrics_view.yaml)
ai_instructions: |
  Chronic absence is defined as missing 10%+ of enrolled days.
  Risk levels: low (<5%), moderate (5-10%), high (>10%).
```

## Evaluation & Quality Gates

### Before Deploying Agent-Generated Changes

1. Run `rill validate` — zero parse errors required
2. Run `rill start` — visual confirmation dashboards render
3. Check that all measures have `description` and `format_preset`
4. Verify no duplicated metric definitions exist
5. Confirm Metrics SQL limitations are respected (no JOINs, no SELECT *)
6. Run project tests: `python -m pytest test_rill_integration.py`

### Golden Conversation Principle

When the agent produces a successful outcome (dashboard created,
query answered correctly), save the conversation as a reference
pattern. These golden conversations become:
- Templates for future similar requests
- Regression tests for agent quality
- Training examples for domain-specific guidance

## Structural Checklist for Every Rill Resource

Before committing any metrics view, model, or dashboard:

```
[ ] Defined as YAML file (not GUI-only)
[ ] Has description field
[ ] display_name uses Title Case
[ ] name uses snake_case
[ ] Measures have format_preset
[ ] Timeseries column is specified
[ ] rill validate passes
[ ] rill start renders dashboards correctly
[ ] No duplicated metric definitions
[ ] ai_instructions added where domain context helps
[ ] Measures use Metrics SQL constraints (no raw table bypass)
```
