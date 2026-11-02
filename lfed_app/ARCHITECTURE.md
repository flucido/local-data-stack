---
id: lfed-app-architecture
type: architecture-design
status: draft
title: Unified local app — generative UI over two on-device models
parent: lfed-architecture
depends-on: [lfed-mod-nl-query, lfed-mod-metrics-bi, lfed-mod-training]
---

## Drivers

Three constraints pick this design, and they are all product constraints rather than study ones.

The claim being tested is that a **2–4B model running on the laptop** can carry an analytics product: turn a question into a query, and turn the result into the right visualization. That is only a claim if the model is making the decisions, so the app must hand real authorship to the model — and bound the damage it can do.

Student data makes "call an API" the wrong answer by default, and a district administrator has no way to configure an endpoint, a port, or a weights file. So the whole thing starts with one command and never asks.

And a number the app prints has to be the number the dashboard prints, which the current client cannot promise (`lfed-docs-known-issues`). The metrics layer stops being advisory here: it is the governed plane.

## Shape

```
┌─ uv run lfed ─────────────────────────────────────────────────────────┐
│                                                                        │
│  browser  http://127.0.0.1:8000  ← static React SPA served by FastAPI  │
│              │                                                          │
│              │ AG-UI over SSE, loopback only (CopilotKit headless)     │
│              ▼                                                          │
│  FastAPI agent ── plane router → executor → validator → envelope → trace│
│     ├── inference: llama.cpp in-process, two slots                     │
│     │      SQL slot (2–4B)              Renderer slot (2B-class, GBNF)  │
│     ├── governed plane: Rill child process, structured metrics query    │
│     └── marts plane: DuckDB read-only through nl_query's guard          │
└────────────────────────────────────────────────────────────────────────┘
```

The browser is a renderer. Every decision that affects a number — which plane answers, what gets executed, whether a generated plan is trustworthy — is made server-side, where it can be validated and traced.

## Modules

| Spec | Boundary |
|---|---|
| `lfed-app` | the package: launch orchestration, config resolution, process supervision, health |
| `lfed-app-agent` | AG-UI agent, plane router, executors, validators, the envelope, HITL |
| `lfed-app-inference` | GGUF backends, the two model slots, grammar construction, memory budget |
| `lfed-app-web` | React SPA, component registry, ask-first canvas, streaming states |
| `lfed-app-observability` | traces without rows, session log, ratings, `/export`, on-device eval |

## Contract

The **answer envelope** is the interface between the agent and the renderer, and the unit a trace describes. It is versioned (`schema_version`) and additive-only: a renderer must degrade to `table` on an unknown version or unknown intent rather than fail.

| Field | Notes |
|---|---|
| `schema_version`, `trace_id` | trace_id is the join key to the trace record |
| `question`, `headline` | headline is model-authored, validated to use only payload numbers |
| `plane` | `governed` \| `marts` — set by the router, never by a model |
| `metrics_view` | present when `plane=governed`; the view that answered |
| `query` | the metrics_query object (governed) or the SQL text (marts) |
| `columns[]` | name, dtype, label, `format_preset` carried from view metadata |
| `rows`, `row_count` | present in the **envelope only**; excluded from every persisted record |
| `viz_plan` | intent + encodings + highlight, from the renderer model or from fallback |
| `viz_source` | `model` \| `fallback` — how the shape was chosen, surfaced in the UI |
| `caveats[]` | kind, message, rows excluded — suppression and plane disclosure |
| `latency_ms` | model / exec / total, split, because the budget is per-stage |
| `fallback_reason` | set when a model plan was rejected |

## Decisions

**CopilotKit as the UI runtime, FastAPI as the agent, no Node runtime.** The React provider is pointed straight at the agent with `selfManagedAgents` — an AG-UI endpoint the app owns and secures itself, which here means bound to loopback with no auth, because the audience is one local user. CopilotKit's TypeScript runtime is the only OSS runtime that works without their cloud "Intelligence" project, and putting a permanently-running second server inside a product whose claim is one transparent local app is the wrong trade. What that gives up, recorded: runtime-side middleware and Intelligence-backed features, and the connection is ours to secure. `@ag-ui/client`'s `HttpAgent` is the seam; a runtime can be introduced later without touching generation.

**Headless primitives, custom canvas.** CopilotKit supplies agent state, tool rendering, and human-in-the-loop; the ask-first canvas is ours. Prebuilt chat components would put the product inside a chatbot shell it is not.

**The rendering model authors the visualization.** It sees the executed result plus the view metadata and emits a viz plan — intent, encodings, which measure to headline, what to highlight, the caption. Grammar-locked sampling built from the plan schema and the actual column list means it cannot name a component that does not exist or a column that is not in the result; a server-side validator still checks dtype sanity and that no number in the headline is absent from the payload. Reject the plan and the deterministic shape classifier answers instead, with `viz_source=fallback` visible to the user and the reason traced. A deterministic if/else picking the chart instead would have made the claim untestable: it would prove a lookup table works.

**Seven intents, closed registry.** `stat`, `bar`, `grouped_bar`, `line`, `area`, `table`, `comparison`, plus a caveat block that rides on any of them. A model cannot request a component that isn't registered, so a wrong plan degrades to a table rather than breaking the render. The registry is the auditable boundary of what the app can draw.

**The server routes the plane; governed answers are structured queries, not SQL text.** The router resolves a question against metrics-view metadata — view, dimension, measure, aliases. Resolved: generate a `metrics_query` object (view, dimensions, measures, filters, order, limit) whose value sets are that view's own metadata, and let Rill execute it. Unresolved: fall through to the marts guard, and mark the answer. Consequences, accepted deliberately: a 2B model fills a constrained object drawn from one view's real dimensions far more often than it writes correct SQL, governed numbers cannot drift from dashboards by construction, and `metrics_view` and `apis/api.yaml` become real work items in `lfed-mod-metrics-bi`. The model never picks the plane and never writes Metrics SQL, so `lfed-docs-known-issues`' retrain recommendation is not a dependency of this app.

**Marts answers are gated; governed answers run.** `plane=marts` renders the generated SELECT first and waits for Run / Edit / Re-ask; cancel executes nothing and traces as `aborted`. Governed answers are aggregate metrics views with suppression already applied upstream, so they stream straight to a chart. The read-only guard makes this a trust decision rather than a safety one, and the friction is spent only where the numbers are ungoverned.

**Grammar-enforced output requires the GGUF backend, so the GGUF backend finally gets built.** `llama-cpp-python` in-process, Metal/CPU auto-selected, one grammar sampler per call (reset between generations), low temperature, bounded max tokens, JSON Schema converted to GBNF. This is the path `README.md` and `ui_strings.py` have described for months without existing in code, and it is what makes "in-process" and "grammar-locked" compatible. The transformers/bnb-4bit path stays as a non-grammar fallback and then loses the guarantee — free JSON plus validator, more fallbacks. `training/README.md`'s missing `modal_export_gguf.py` is the prerequisite for a small GGUF (`lfed-mod-training`).

**Contract-first model binding.** The agent depends on two protocols — a SQL backend (`question, schema → streamed SQL`) and a viz backend (`result, view_meta → viz plan`) — with a sizing requirement attached (resident ≤ 8 GB on a 16 GB machine, first-run download 2–6 GB, < 3 s to first token). No checkpoint id, LoRA rank, or quantization level appears anywhere in this graph; the retrain runs in parallel in `lfed-mod-training` and drops in behind the protocol. `lfed-mod-nl-query`'s `TransformersLLM`-mimicking-`llama_cpp` seam is the precedent for this.

**Launch is `uv run lfed`.** Resolve or download weights, start Rill and FastAPI as hidden children, wait for health, open the browser, and show a health panel when something failed. No npm step for the user (the SPA bundle is built and vendored), no `.app`/`.dmg`, no non-macOS target (`lfed-app`).

**The app opens with a synthetic district, not the sample.** Five-row synthetic Parquet can't produce a chart or trip suppression. Default warehouse: a plausible multi-year district (~15 schools, 3–4 academic years) loaded through the real dlt/dbt path so the schema and k≥5 behavior are identical to production, deterministic so demos and fixtures agree, with the warehouse-resolution chain of `lfed-mod-nl-query` still pointing at a user's real warehouse when one exists. **The owner is supplying the actual synthetic-district dataset; its contents are not yet reviewed here** — the requirement is specced, the file is pending input.

**Gradio retires at parity; Rill stops being a UI.** The four dashboards are rebuilt natively so browsing and asking share one surface, one design system, and the same suppression disclosure. Rill remains the governed plane's executor and the source of metric definitions — it is hidden as a window, not deleted as a dependency.

## Invariants

- **No egress.** No cloud inference, no CopilotKit Intelligence, telemetry disabled in the runtime environment (`COPILOTKIT_TELEMETRY_DISABLED=true`), and after first-run weight download the request path touches no network.
- **Rows never reach storage.** Traces, session logs, and exports record the question, query, plane, intent, `viz_source`, latency, rating — the envelope's `rows` field exists only in flight to the browser.
- **Plane is never silent.** An ungoverned answer carries a visible provenance mark and a `plane=marts` record; two answers to the same question with different provenance never look identical.
- **The guard is inherited, not copied.** Marts execution calls into `nl_query`'s read-only, allowlisted, `EXPLAIN`-validated, capped, timed path, so `nl_query`'s guard tests remain the contract for this app.
- **No client-side execution authority.** The browser renders envelopes and sends intents; it never holds a connection to the warehouse or the metrics layer.
- **One command, zero configuration.** Env overrides exist for development; nothing about a port, endpoint, model path, or weights file is required of the person using it.
- **Suppression is reported, never implied.** Both upstream regimes — dbt's dropped k<5 groups and CDE's `is_suppressed` flag — surface as caveats, because a client cannot recover rows the warehouse discarded.

## Out of scope

Saved boards, pinning, persistence across launches, and sharing; authentication, per-school row-level security, and multi-tenant or hosted deployment; packaged `.app`/`.dmg` and non-macOS builds; consent flows, reviewer queues, and anything else study-shaped; choosing or training the checkpoints; replacing dbt, the marts, or the metrics-view governance itself. Agentic tool-calling chat, MCP surfaces, RAG, and fine-tuning-in-the-loop are all non-goals that the "two model slots, one envelope" design is specifically there to keep out.
