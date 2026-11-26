# Sovereign Local-First Desktop Shell & Generative UI Engine

This directory contains the production native desktop host and Generative UI workspace for the **Sovereign Local-First Analytics & Generative UI Engine**.

## Architecture Overview

```mermaid
flowchart TD
    subgraph UI ["Desktop Webview (React 19 + TypeScript + Vite)"]
        UI_Input["User Natural Language Query / Scenario Selector"]
        TwoHop_Trace["Two-Hop Inspector Drawer"]
        GenUI_Registry["Canonical Component Registry\n(KPIGrid, TimeSeriesChart, CategoryBarChart, BudgetVarianceChart, DataTable, FilterBar)"]
        Arrow_Client["Zero-Copy Arrow Client (tableFromIPC)"]
    end

    subgraph Native ["Rust Host (Tao + Wry Native Shell)"]
        IPC_Bridge["Bidirectional JSON-RPC Bridge (window.ipc)"]
        Arrow_Protocol["Custom Protocol Handler ('arrow://')"]
        Schema_Pruner["BM25 + 1-Hop FK Join Schema Pruner"]
        Agent_Loop["Two-Hop + Self-Healing Agent Loop (llama-server / fallback)"]
    end

    subgraph Storage ["Medallion Local Data Engine"]
        Bronze_SQLite["Bronze SQLite (ACID Ingestion & Overrides)"]
        Silver_Gold_DuckDB["DuckDB In-Memory (Silver / Gold Analytical Layer)"]
        Edu_DuckDB["Read-Only Analytics Warehouse (analytics.duckdb)"]
    end

    UI_Input -->|"window.sendRustRpc({cmd: 'run_prompt'})"| IPC_Bridge
    IPC_Bridge --> Agent_Loop
    Agent_Loop --> Schema_Pruner
    Agent_Loop --> Silver_Gold_DuckDB
    Silver_Gold_DuckDB -->|Arrow IPC Stream| Arrow_Protocol
    Arrow_Protocol -->|fetch('arrow://query_id')| Arrow_Client
    Arrow_Client --> GenUI_Registry
    GenUI_Registry -->|FilterBar Mutation| IPC_Bridge
    IPC_Bridge -->|Parameterized CTE| Silver_Gold_DuckDB
    Bronze_SQLite -->|Reactive Sync| Silver_Gold_DuckDB
    Edu_DuckDB -.->|0600 snapshot, ATTACH READ_ONLY, materialize| Silver_Gold_DuckDB
```

An interactive, source-linked version of this hot path (question → `run_prompt` IPC → two-hop agent loop → DuckDB → `arrow://` render) is available as the [desktop two-hop sequence diagram](../docs/diagrams/sequence-desktop-two-hop.html), also listed in the [diagram index](https://flucido.github.io/local-data-stack/diagrams/).

1. **Native Host (`desktop/src/`)**:
   - **Tao + Wry**: Native macOS windowing with cross-platform WebKit integration.
   - **Medallion Engine (`medallion.rs`)**: Synchronizes Bronze SQLite ACID writes (`bronze_k12.db`) into in-memory DuckDB analytical tables, then copies the K-12 education warehouse (`analytics.duckdb`) to a mode-0600 snapshot, attaches it read-only, materializes the allowed `main_core`/`main_analytics` tables with PII columns stripped, and deletes the snapshot.
   - **Zero-Copy Arrow IPC (`ipc.rs`)**: Custom `arrow://` URI protocol handler serving raw Apache Arrow binary streams directly to the frontend without JSON serialization overhead.
   - **Two-Hop Agent Loop (`agent_loop.rs`)**: Implements the continuous ChatML conversation loop reusing in-process KV-cache across Hop 1 (SQL), Hop 1b (self-healing `BinderError` retries), and Hop 2 (dynamic GBNF Generative UI binding).

2. **Generative UI Workspace (`desktop/ui/`)**:
   - **React 19 + Vite + TypeScript**: Minimal, zero-cloud desktop application.
   - **Canonical Component Registry (`components/registry/`)**:
     - `KPIGrid`: 1–4 scalar metrics with delta badges and formatting.
     - `TimeSeriesChart`: Stacked bar, line, and area charts over temporal X-axes.
     - `CategoryBarChart`: Horizontal, vertical, and grouped categorical breakdowns.
     - `BudgetVarianceChart`: Actual-versus-budget bars with variance formatting.
     - `DataTable`: Responsive TanStack Table with multi-column sorting and CSV export.
     - `FilterBar`: Date range, multi-select, numeric range, and search controls.
   - **Zero-LLM Parameterized CTEs**: Modifying filters executes `WITH _base AS (<query>) SELECT * FROM _base WHERE ...` in DuckDB with zero model inference calls; the UI displays the measured filter latency.

---

## Running the Interactive Human Test Environment

### Method 1: Sovereign Native Desktop App (Recommended)

To run the full native macOS application:

```bash
# 1. Build the production UI bundle
cd desktop/ui
npm install
npm run build
cd ../..

# 2. Run the native host application
cargo run --manifest-path desktop/Cargo.toml
```

**What to test as a human user** (a structured, scored version of this is [`HUMAN_TEST_PLAN.md`](./HUMAN_TEST_PLAN.md)):
- **Ask a Question**: Type a plain-English question in the "Ask a question" box and press **Get answer** (or ⌘/Ctrl+Enter). The frontend sends `{cmd: "run_prompt", prompt}` over the Wry bridge; the Rust host runs the full two-hop agent loop (schema pruning → Hop 1 SQL → self-healing → Hop 2 GenUI) and streams the result back over `arrow://`.
  > **Note**: `ipc.rs` routes `run_prompt` through `LocalSlmBackend`, which uses a loopback `llama-server` (default `http://127.0.0.1:8080`, override with `LFED_SLM_ENDPOINT`) when one is running, and otherwise falls back to the `DeterministicTwoHopBackend` keyword stub in `agent_loop.rs` (`mode: "deterministic_demo"`, surfaced as a "Demo Mode" badge in the header). To exercise the real model-backed engine, start llama-server with `models/lfed-lfm3-1.7b-two-hop-Q8_0.gguf` first (see the [human test plan](./HUMAN_TEST_PLAN.md) setup section). Preset scenarios are unaffected.
- **Analytical Scenarios**: Click preset buttons (`Multi-Year School Enrollment`, `Equity Outcomes by Race`, `CDE Subgroup Accountability`).
- **Two-Hop Protocol Inspector**: Click **"Show technical details"** to view the Hop 1 tool call and SQL, the DuckDB result summary, and the Hop 2 component payload.
- **Zero-LLM Filter Interaction**: Click a pill or adjust a slider in the `FilterBar` and read the measured filter latency badge.
- **Data Table Interactivity**: Sort columns, filter rows, or inspect exact student metrics.

### Method 2: Browser Dev Workspace (Instant Hot-Reload)

To run in a standard web browser with hot module replacement:

```bash
cd desktop/ui
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Preset reports use seeded rows and a client-side Arrow simulation when running outside the native Wry host; free-text asking reports that it requires the native host.

---

## Automated Verification

```bash
# Run Rust unit tests (IPC, Medallion, GBNF compiler, Schema pruner, Agent loop)
cargo test --manifest-path desktop/Cargo.toml

# Run React component registry and Arrow IPC tests
npm --prefix desktop/ui run test

# Type-check and build production webview assets
npm --prefix desktop/ui run build
```
