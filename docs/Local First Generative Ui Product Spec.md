# Product Specification & Technical Blueprint: Sovereign Local-First Analytics & Generative UI Engine

## 1. Product Vision Unifies Local Medallion Analytics with Dynamic Generative Interfaces

This specification defines a standalone, zero-cloud desktop application that merges two existing workstreams—the **Local Data Stack** (SQLite-to-DuckDB analytical backend currently accessed via terminal CLI or a prototype Gradio interface) and the **Personal Finance & Budget Application** (generative UI currently backed by a cloud Qwen model)—into a single reusable, privacy-first desktop platform.

Every layer of the stack—transactional ingestion, columnar analytics, small language model (SLM) inference, and dynamic UI component rendering—executes locally on the user's machine. User financial records, analytical tables, and model prompts never leave the local filesystem.

| Product Dimension | Legacy Prototype State | Target Production Architecture |
| :--- | :--- | :--- |
| **Application Shell** | Terminal CLI / Hugging Face Gradio web wrapper | Standalone Rust binary via [Tao](https://docs.rs/tao) windowing and [Wry](https://docs.rs/wry) OS-native webview |
| **Data Pipeline** | Manual CLI scripts moving data from SQLite to DuckDB | Automated in-process Medallion pipeline ([Rusqlite](https://docs.rs/rusqlite/) Bronze to [DuckDB](https://docs.rs/duckdb/) Silver/Gold) |
| **Data Transport** | JSON serialization over HTTP | Zero-copy [Apache Arrow](https://docs.rs/arrow/latest) binary streams over custom Wry IPC protocols |
| **UI Paradigm** | Static Gradio blocks or cloud-dependent [CopilotKit](https://docs.copilotkit.ai/) chat | Local schema-driven Generative UI registry using [Vercel AI SDK](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces) patterns |
| **AI Inference** | Cloud Qwen API or 14B single-turn NL→SQL adapter (`~9 GB` GGUF) | Quantized 1.5B–3B SLM ([Liquid AI LFM2.5 / LFM3](https://docs.liquid.ai/lfm/fine-tuning/overview) or [Qwen2.5-Coder / Qwen3](https://huggingface.co/Qwen)) via [llama.cpp](https://github.com/ggml-org/llama.cpp) |
| **Distribution** | Python environment / local dev server | Single compiled native binary (~15–25 MB) + sideloaded `Q8_0` / `Q6_K` `.gguf` model pack (~1.6–2.4 GB) |

## 2. System Infrastructure Connects Rust, DuckDB, and Native Webviews Without Electron Overhead

The infrastructure eliminates Chromium bundling (Electron) and opinionated framework boilerplate (Tauri) by pairing a lightweight Rust host process directly with the operating system's native web rendering engine.

### 2.1 Host Runtime & Windowing Layer (Rust + Tao + Wry)

* **Cross-Platform Window Management**: [Tao](https://docs.rs/tao) manages the native application event loop, window creation, menu bars, and OS lifecycle events across macOS, Windows, and Linux.
* **OS-Native Webview Rendering**: [Wry](https://docs.rs/wry) binds the window handle to the host OS web engine (`WKWebView` on macOS, `WebView2` on Windows, `WebKitGTK` on Linux) via [`WebViewBuilder`](https://docs.rs/wry/latest/wry/struct.WebViewBuilder.html).
* **Bidirectional Asynchronous IPC**:
  * **Control Channel (`window.ipc.postMessage`)**: Handles lightweight JSON-RPC commands from the frontend (e.g., user prompts, filter mutations, ingestion triggers, UI state snapshots).
  * **Bulk Data Channel (`with_custom_protocol`)**: Registers a custom `arrow://` protocol handler in Wry. When the frontend requests query results, Rust streams raw [Apache Arrow](https://docs.rs/arrow/latest) RecordBatches directly into WebAssembly/JavaScript memory with zero JSON parsing overhead.

### 2.2 Local Medallion Data Architecture (SQLite to DuckDB)

* **Bronze Layer — Transactional Ingestion ([Rusqlite](https://docs.rs/rusqlite/))**:
  * Ingests raw CSVs, OFX/QFX bank feeds, JSON payloads, and user annotations into a local `bronze.db` SQLite file.
  * Guarantees ACID transaction safety for point-in-time writes, user edits, and manual category overrides (critical for the Personal Finance Budget workflow).
* **Silver Layer — Cleaned & Normalized Relational Views ([DuckDB](https://docs.rs/duckdb/))**:
  * Embedded DuckDB attaches directly to `bronze.db` using its native SQLite scanner extension (`INSTALL sqlite; LOAD sqlite; ATTACH 'bronze.db' AS bronze (TYPE SQLITE);`).
  * Incremental SQL transformations deduplicate records, standardize timestamps and currency types, and materialize cleaned tables into local Zstd-compressed Parquet files.
* **Gold Layer — Analytical Marts & Schema Registry**:
  * Pre-computes domain-specific rollups (e.g., `gold_monthly_cashflow`, `gold_merchant_spend_velocity`, `gold_cohort_metrics`, `mart_cde_school_accountability`) and stores a compact JSON/DDL **Schema Catalog** (including column types, semantic descriptions, and top enum sample values) used as context for the local language model.

### 2.3 Generative UI Layer & Canonical Component Registry

Rather than rendering free-form markdown chat or relying on heavy middleware like [LangChain](https://www.langchain.com/) or [Microsoft Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-architecture), the frontend operates as a deterministic **Generative UI Engine** built in React or Svelte:

* **Custom Local Provider Adapter**: Implements the open-source [Vercel AI SDK Custom Provider](https://ai-sdk.dev/providers/community-providers/custom-providers) specification over Wry IPC, allowing standard `useChat` / streaming tool-call hooks to run completely offline against the local model.
* **Canonical Component Registry Contract**: The model never generates raw HTML/JSX. In Hop 2, it emits a single structured `render_workspace_ui` tool call containing an array of 1–4 layout panels mapped to a strongly typed registry of pre-built UI components validated by Zod schemas:
  * `KPIGrid`: Displays 1–4 scalar summary metrics (bound to single-row query columns) with optional period-over-period delta badges and formatting hints (`currency`, `percent`, `integer`).
  * `TimeSeriesChart`: Renders interactive line, area, or stacked bar charts over a temporal X-axis (`DATE` / `TIMESTAMP` column) and 1–3 numeric Y-axis series bound to an `arrow://query_id` handle.
  * `CategoryBarChart`: Renders horizontal or grouped bar charts comparing categorical breakdowns (e.g., spend by merchant, attendance by school subgroup).
  * `BudgetVarianceChart`: Specialized bullet/variance component comparing actual vs. target/budgeted values across categories.
  * `DataTable`: Mounts a virtualized, sortable data grid (TanStack Table) bound to the `arrow://query_id` stream with column formatting, inline search, and CSV export.
  * `FilterBar`: Injects interactive UI controls (date-range pickers, enum multiselects, numeric sliders) bound to specific column names and data types.
    * *Zero-LLM Filter Execution*: When a user changes a `FilterBar` control, the frontend does **not** re-run the SLM. Instead, it sends a lightweight `apply_query_filters` RPC to Rust, which wraps the cached base SQL query in a parameterized outer CTE (`WITH _base AS (<validated_sql>) SELECT * FROM _base WHERE ...`) using DuckDB prepared statements and streams an updated `arrow://` RecordBatch in `< 15ms`.

### 2.4 Local Inference Topology Comparison: Native Rust vs. In-Webview WebGPU

Your architecture discussions explored two viable ways to execute the local small language model. While both work, **Topology B (In-Process Rust Native Execution)** is strongly recommended as the primary production path for data analysis workloads.

| Architectural Criteria | Topology A: In-Webview Execution ([WebLLM](https://webllm.mlc.ai/) / WebGPU) | Topology B: In-Process Native Rust ([llama.cpp](https://github.com/ggml-org/llama.cpp) / [Candle](https://github.com/huggingface/candle)) |
| :--- | :--- | :--- |
| **Execution Context** | Inside the Wry webview via browser WebGPU + WASM | Inside the Rust host binary via C++/Rust FFI bindings |
| **Hardware Acceleration** | Browser WebGPU API (Dawn / wgpu) | Native Metal (macOS), Vulkan, CUDA, AVX2/NEON |
| **DuckDB Integration** | Requires round-trip IPC from JS to Rust to test SQL queries | Direct in-process memory access to DuckDB for self-healing SQL loops |
| **Memory & VRAM Overhead** | Constrained by webview tab memory limits (~4 GB ceiling on some platforms) | Full access to system RAM/VRAM with `mmap` zero-copy weight loading |
| **Constrained Decoding** | Basic JSON mode support | Full GBNF grammar enforcement guaranteeing 100% valid JSON envelopes & UI schemas |
| **Best Fit Use Case** | Lightweight UI-only assistants or browser-portable builds | **Recommended**: Coupled Text-to-SQL + Generative UI desktop apps |

### 2.5 End-to-End Execution, KV-Cache Reuse & Self-Healing Query Loop

To achieve sub-second responsiveness on consumer hardware, the two-pass agent loop executes as a **single continuous multi-turn conversation in `llama.cpp`**, preserving the KV cache across hops so the system prompt and DDL schema are evaluated only once per session:

1. **User Intent**: The user types or clicks an exploration prompt (e.g., *"Show me recurring subscriptions that increased in price over the last 6 months"*).
2. **Context Assembly, Top-K Schema Pruning & Prefix Cache (Rust)**:
   * Sub-3B models lose column-name attention if all 30+ warehouse tables (~4,000 tokens of DDL) are dumped into every prompt. Before Hop 1, the Rust orchestrator performs fast deterministic **Top-K Schema Pruning** (scoring table/column descriptions + foreign-key join paths via BM25/keyword matching to select the 4–6 relevant Silver/Gold tables, keeping DDL context under ~800 tokens).
   * The static system prompt and selected DDL catalog are evaluated in the `llama.cpp` KV cache and reused across both hops within the turn.
3. **Hop 1 — Constrained SQL Generation (`execute_duckdb_query`)**:
   * Constrained by a Hop 1 `.gbnf` grammar that enforces a valid JSON tool call and a read-only `SELECT`/`WITH` SQL prefix, the SLM emits `execute_duckdb_query({ sql, explanation })`.
   * Rust validates the SQL for read-only safety and executes it against DuckDB in-process.
   * *Hop 1b — Self-Healing Guardrail*: While GBNF guarantees valid JSON structure, it cannot validate relational semantics (e.g., column scoping across joins). If DuckDB returns a binder or syntax error, Rust appends a `<|im_start|>tool` error turn containing the exact DuckDB error message (which includes DuckDB's built-in `Candidate bindings` hint) and re-samples `execute_duckdb_query` (capped at 2 retries) before the user ever sees a failure.
4. **Hop 2 — Generative UI Selection (`render_workspace_ui`)**:
   * Once DuckDB returns a valid relation, Rust materializes the Arrow RecordBatch in memory, registers an `arrow://query_id` handle, and computes a compact ~150-token **Result Metadata Summary** (column names, DuckDB logical types, total `row_count`, null ratios, numeric min/max bounds, and up to 3 sample rows).
   * Rust appends this summary as the `<|im_start|>tool` response directly onto the active KV cache from Hop 1 and switches the sampler to the Hop 2 `.gbnf` grammar.
   * The SLM emits `render_workspace_ui({ title, narrative_summary, components: [...] })`, selecting 1–4 components from the registry and binding exact output column names to chart axes, KPI cards, and `FilterBar` controls.
5. **Zero-Copy Render**: Rust sends the `render_workspace_ui` JSON payload alongside the `arrow://query_id` handle to the webview. The React/Svelte registry mounts the interactive charts and data grid in under 50ms.

## 3. Software Stack, Engineering Phases, and Time-and-Material Requirements Define the Build

### 3.1 Software Bill of Materials (SBOM)

| Layer | Package / Crate / Tool | Role in Architecture | License |
| :--- | :--- | :--- | :--- |
| **Rust Host & Windowing** | [`tao`](https://docs.rs/tao) + [`wry`](https://docs.rs/wry) | Cross-platform window event loop and native OS webview | Apache-2.0 / MIT |
| **Async & Serialization** | `tokio`, `serde`, `serde_json` | Non-blocking runtime for parallel DB queries and LLM streaming | MIT |
| **Storage & Analytics** | [`rusqlite`](https://docs.rs/rusqlite/) + [`duckdb`](https://docs.rs/duckdb/) (`bundled`) | Embedded SQLite (Bronze) and DuckDB (Silver/Gold) engines | MIT |
| **Columnar Transport** | [`arrow`](https://docs.rs/arrow/latest) + `arrow-ipc` (Rust & JS) | Zero-copy binary serialization between DuckDB and webview | Apache-2.0 |
| **Local LLM Engine** | [`llama.cpp`](https://github.com/ggml-org/llama.cpp) (`llama-cpp-2` crate) | Quantized GGUF model execution, KV-cache reuse, GBNF grammars | MIT |
| **Frontend Framework** | React 19 or Svelte 5 + TypeScript + Vite | Reactive UI state management and fast static asset bundling | MIT |
| **GenUI & Validation** | [Vercel AI SDK Core](https://ai-sdk.dev/docs/introduction) + `zod` | Tool-call stream parsing and strict component prop validation | Apache-2.0 / MIT |
| **Visualization Kit** | Vega-Lite / ECharts / TanStack Table | Declarative charts and virtualized 100k+ row data grids | BSD / MIT |

### 3.2 Phased Engineering Roadmap & Effort Estimates

Assuming you already have the core SQLite-to-DuckDB analytical queries and initial NL→SQL evaluation harness (`nl_query/` and `training/`) working in your Local Data Stack project and UI patterns prototyped in your Personal Finance project, the engineering effort focuses on unification, the Wry IPC bridge, the Generative UI registry, and evolving the training pipeline from a single-turn 14B SQL model to a 2-hop 1.5B–3B SQL + GenUI model.

| Phase | Milestone & Key Deliverables | Engineering Scope | Solo Builder (Part-Time ~20h/wk) | Solo Builder (Full-Time ~40h/wk) | Estimated Engineering Hours |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: Core Shell & Data Bridge** | Replace Gradio with Rust (`tao` + `wry`), embed `rusqlite` + `duckdb`, implement custom `arrow://` IPC protocol & parameterized filter CTEs | Rust backend, Vite static embedding, Arrow JS table loader | 3–4 weeks | 1.5–2 weeks | 65–80 hrs |
| **Phase 2: Generative UI Registry** | Build dynamic React/Svelte component registry (`KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, `FilterBar`) + Zod/GBNF generator | Frontend architecture, custom Vercel AI SDK IPC provider | 3–4 weeks | 1.5–2 weeks | 70–85 hrs |
| **Phase 3: Local SLM & Agent Loop** | Embed `llama.cpp` in Rust, implement KV-cache prefix reuse, GBNF grammar switching, and 2-hop self-healing DuckDB SQL + UI loop | Rust FFI bindings, prompt templates, KV-cache session state | 4–5 weeks | 2–2.5 weeks | 80–100 hrs |
| **Phase 4: Model Training & Packaging** | Curate 2-hop + error-recovery dataset, Modal `bf16` Full Fine-Tune / DoRA on 1.5B–3B SLM, `Q8_0`/`Q6_K` `imatrix` GGUF export & OS installers | Modal GPU pipeline (`transformers` + `trl` + `FlashAttention-2` + `Liger-Kernel`), `.dmg` / `.msi` | 4–5 weeks | 2–2.5 weeks | 75–95 hrs |
| **Total Build** | **Production-Ready v1.0 Desktop Binary** | **End-to-End Stack** | **14–18 weeks** | **7–9 weeks** | **290–360 hrs** |

### 3.3 Time-and-Material (T&M) Cost Breakdown

Because the runtime is 100% local and built entirely on permissive open-source libraries, **ongoing cloud inference and database hosting costs are $0/month**.

| Cost Category | Itemized Requirement | DIY / Solo Developer Cost | Contract / Assisted Build Cost | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Software Licenses** | Rust crates, DuckDB, SQLite, React/Svelte, llama.cpp | **$0** | **$0** | 100% MIT / Apache-2.0 open-source stack |
| **Synthetic Data Generation** | Teacher LLM runs (Modal vLLM `Qwen2.5-72B` or frontier API) for 3,000 multi-turn trajectories | **$15 – $40** | **$40 – $100** | One-time dataset synthesis cost |
| **Cloud GPU Training Compute** | Modal NVIDIA A100-80GB or H100 for 10–20 total hours of `bf16` Full Fine-Tuning / DoRA + GGUF `imatrix` exports | **$25 – $75** | **$75 – $175** | Native `bf16` training on Modal (no 4-bit QLoRA compromises) |
| **OS Code Signing & Notarization** | Apple Developer Program ($99/yr) + Windows OV/EV Code Signing ($120–$300/yr) | **$220 – $400 / yr** | **$220 – $400 / yr** | Required only when distributing binaries to external users |
| **Engineering Labor (Optional)** | ~320 hours of Rust + React/Svelte + ML engineering (if hiring contractors at $100–$150/hr) | **$0** (Sweat equity) | **$32,000 – $48,000** | Can be modularized (e.g., hire out only Wry shell or UI components) |
| **Total Cash Outlay** | **Prototype to Distributable v1.0** | **$35 – $100** (pre-signing) / **$300 – $500** (signed) | **$32,320 – $48,650** | Zero recurring per-user server costs |

## 4. Model Training Pipeline Adapts 1.5B–3B Small Models for Deterministic SQL and UI Generation

### 4.1 Evolution from the v1 14B NL→SQL Adapter to a 1.5B–3B Two-Hop Engine

The repository currently includes a working v1 training and evaluation pipeline (`training/generate_pairs.py`, `training/modal_generate.py`, `training/modal_export_gguf.py`, and `nl_query/eval.py`) that fine-tuned `Qwen2.5-Coder-14B-Instruct` (`r=64` LoRA, `~9.0 GB` `Q4_K_M` GGUF) on single-turn NL→SQL pairs. While effective on 16–32 GB machines, a 9 GB model is too heavy for fast multi-pass Generative UI on standard 8–16 GB laptops.

By decomposing the problem into a deterministic **Two-Hop Tool-Calling Protocol** and enforcing structural validity via GBNF grammars, a **1.5B–3B parameter model** can match or exceed the 14B model's task accuracy at **5x–8x faster token generation** and **one-fifth the memory footprint (~1.1–1.8 GB)**:

* **Primary Base Model Candidates**:
  1. **Qwen2.5-Coder-1.5B-Instruct / Qwen2.5-Coder-3B-Instruct** (or **Qwen3-1.7B / 4B**): Strong pre-training on SQL dialects, JSON schemas, and code repair.
  2. **Liquid AI LFM2.5-1.2B-Instruct / LFM2-2.6B** (or **LFM3-1.7B**): Hybrid short-convolution + grouped-query attention architecture optimized specifically for low-memory edge prefill speed and high tool-calling accuracy ([95%+ tool-call equivalence after fine-tuning](https://www.distillabs.ai/blog/fine-tuning-liquids-lfm25-accurate-tool-calling-at-350m-parameters/)).

### 4.2 Canonical Two-Hop Tool & Trajectory Specification

Small models fail when asked to do open-ended reasoning, invent SQL, and write arbitrary UI code simultaneously. Instead, every training example follows a strict ChatML multi-turn conversation trajectory where the model only ever emits two structured tool calls.

#### Turn 1 (System + User → Assistant Hop 1: `execute_duckdb_query`)
* **Input**: Compact DDL of relevant Silver/Gold tables (column names, DuckDB types, short descriptions, and up to 3 sample enum values) + user question (or multi-turn follow-up).
* **Assistant Output (Constrained by `hop1_sql.gbnf`)**:
```json
{
  "tool": "execute_duckdb_query",
  "arguments": {
    "explanation": "Aggregate monthly spending by category over the last 6 months using DATE_TRUNC.",
    "sql": "SELECT DATE_TRUNC('month', transaction_date) AS spend_month, category, ROUND(SUM(amount), 2) AS total_spend FROM main_analytics.gold_monthly_cashflow WHERE transaction_date >= CURRENT_DATE - INTERVAL '6 months' GROUP BY 1, 2 ORDER BY 1 ASC, 3 DESC"
  }
}
```

#### Turn 1b (Optional Conditional Branch: Self-Healing SQL Recovery)
* **Trigger**: Only occurs if DuckDB returns a binder, catalog, or syntax error on Turn 1.
* **Tool Input (`duckdb_execution_error`)**:
```json
{
  "status": "error",
  "error_type": "BinderError",
  "message": "Referenced column \"transaction_date\" not found in FROM clause! Candidate bindings: \"txn_month\", \"merchant_category\", \"net_amount\""
}
```
* **Assistant Output**: A corrected `execute_duckdb_query` tool call binding the valid columns (`txn_month`, `merchant_category`, `net_amount`).

#### Turn 2 (Tool Metadata Summary → Assistant Hop 2: `render_workspace_ui`)
* **Tool Input (`duckdb_result_summary` injected by Rust after successful execution)**:
```json
{
  "status": "ok",
  "query_id": "q_8f3a19",
  "row_count": 36,
  "columns": [
    { "name": "spend_month", "type": "DATE", "min": "2026-05-01", "max": "2026-10-01", "distinct_count": 6 },
    { "name": "category", "type": "VARCHAR", "sample_values": ["Groceries", "Dining Out", "Utilities"], "distinct_count": 6 },
    { "name": "total_spend", "type": "DOUBLE", "min": 84.50, "max": 1420.00, "null_count": 0 }
  ],
  "sample_rows": [
    ["2026-05-01", "Groceries", 812.40],
    ["2026-05-01", "Dining Out", 415.20],
    ["2026-05-01", "Utilities", 195.00]
  ]
}
```
* **Assistant Output (Constrained by `hop2_ui.gbnf`)**:
```json
{
  "tool": "render_workspace_ui",
  "arguments": {
    "title": "6-Month Category Spend Trend",
    "narrative_summary": "Groceries and Dining Out account for the largest monthly spend across the past 6 months.",
    "components": [
      {
        "component": "FilterBar",
        "controls": [
          { "column": "spend_month", "control_type": "date_range", "label": "Month Range" },
          { "column": "category", "control_type": "multi_select", "label": "Category" }
        ]
      },
      {
        "component": "TimeSeriesChart",
        "chart_variant": "stacked_bar",
        "x_column": "spend_month",
        "y_columns": ["total_spend"],
        "series_column": "category",
        "value_format": "currency"
      },
      {
        "component": "DataTable",
        "columns": ["spend_month", "category", "total_spend"],
        "default_sort": { "column": "spend_month", "direction": "desc" }
      }
    ]
  }
}
```

### 4.3 Step-by-Step Training & Testing Workflow

#### Step 1: Establish a Zero-Shot Baseline with Constrained Decoding (Before Training)
Per [Liquid AI's Fine-Tuning Guidelines](https://docs.liquid.ai/lfm/fine-tuning/overview), always evaluate the base model with **GBNF grammar constraints** in `llama.cpp` before running SFT:
* **Scope of GBNF vs. Runtime Verification**:
  * Convert the Hop 1 (`execute_duckdb_query`) and Hop 2 (`render_workspace_ui`) Zod schemas into `.gbnf` grammar files.
  * For **Hop 2**, dynamic GBNF generation (injecting the exact column names returned by DuckDB into the `.gbnf` column enum rule before sampling Hop 2) makes the base model **physically incapable** of outputting malformed JSON, hallucinating component names, or binding non-existent column names to chart axes.
  * For **Hop 1**, GBNF enforces the JSON envelope and `SELECT`/`WITH` prefix, while DuckDB's in-process execution engine validates relational semantics.
* Run the base 1.5B–3B model against an initial 50-prompt benchmark across your Education (`analytics.duckdb`) and Personal Finance schemas to log baseline failure modes (e.g., DuckDB date math, `reporting_category` filtering, or poor chart-type selection).

#### Step 2: Synthetic Dataset Curation (3,000 Verified Multi-Turn Trajectories)
Extend the existing `training/generate_pairs.py` and `training/modal_generate.py` scripts from single-turn SQL generation to full multi-turn trajectories in Hugging Face `messages` + `tools` JSONL format:

* **Critical Fix 1 Over v1 `modal_generate.py` (Seeded Validation Warehouses)**:
  * In v1 `training/modal_generate.py`, SQL validation ran against an in-memory DuckDB populated with a single `NULL` dummy row per table. While sufficient to catch syntax errors for Hop 1, `NULL`-only tables return `0 rows` on `WHERE` filters and `NULL` min/max bounds—which breaks Hop 2 UI component selection because the model cannot distinguish a 1-row scalar KPI result from a 500-row time series!
  * **Requirement**: Synthetic generation MUST execute against **seeded DuckDB files containing realistic synthetic rows** (1,000–10,000 rows per table across 10–15 schemas: K-12 Education `analytics.duckdb`, Personal Finance & Budget tables, plus 8–10 diverse public analytical schemas such as e-commerce, SaaS metrics, and healthcare) so `duckdb_result_summary` contains realistic `row_count`, `distinct_count`, `min`/`max` bounds, and `sample_rows`.
* **Critical Fix 2 Over v1 `generate_pairs.py` (Top-K Pruned DDL Contexts with Hard-Negative Distractors)**:
  * To match the Rust runtime's **Top-K Schema Pruner** (Recommendation 3) and prevent train/inference mismatch, training examples MUST NOT inject all 30+ warehouse tables into the system prompt.
  * For every generated training example, construct the system prompt's DDL block with **4 to 6 tables** (~600–800 tokens): the **1–2 gold tables** referenced by the target SQL query, plus **3–4 hard-negative distractor tables** selected by running the same BM25/keyword + foreign-key pruner against the user question, shuffled in random order. This explicitly trains the 1.2B–3B model's attention heads to discriminate the correct table and join keys from closely related sibling tables.
* **Three Mandatory Dataset Splits (3,000 Total Trajectories)**:
  1. **Split A — Golden 2-Hop Trajectories (70% / ~2,100 examples)**: `System + DDL` → `User Question` → `Hop 1 SQL` → `DuckDB Result Summary` → `Hop 2 UI Layout` across 5 prompt archetypes:
     * Single-metric KPI lookups (*"What was my net savings rate in Q3?"* → `KPIGrid`)
     * Temporal trend comparisons (*"Compare grocery vs. dining spend month-over-month"* → `TimeSeriesChart` + `FilterBar`)
     * Categorical & variance breakdowns (*"How did actual spend compare to budget by category?"* → `BudgetVarianceChart` / `CategoryBarChart`)
     * Anomaly & entity-level drilldowns (*"Show transactions over 2x the category average"* → `DataTable` + `KPIGrid`)
     * Multi-metric executive overviews (*"Give me a 2023-24 district accountability overview for Hispanic students"* → `KPIGrid` + `CategoryBarChart` + `DataTable`)
  2. **Split B — Self-Healing Error-Recovery Trajectories (15% / ~450 examples)**:
     * Rather than discarding *all* failed SQL queries during synthesis, intentionally capture failed teacher/student SQL attempts (or synthetically perturb column/table names and DuckDB date syntax), execute them against DuckDB to capture the real `BinderError` / `ParserError` message, and append the recovery turn (`Turn 1b` → corrected `execute_duckdb_query` → `Turn 2` UI).
     * This explicitly trains the 1.5B–3B model to read DuckDB's `Candidate bindings` hints and self-correct on the first retry.
  3. **Split C — Conversational Follow-Up & Refinement Trajectories (15% / ~450 examples)**:
     * 2-turn user conversations where the user refines a prior query (*"Now break that down by payment method"* or *"Exclude recurring rent payments"*), training the model to modify the prior SQL and update the workspace UI layout smoothly.
* **Automated Execution & Semantic Verification Gate**:
  * Every trajectory's final SQL must execute cleanly in DuckDB (`row_count >= 1`), every `render_workspace_ui` call must pass Zod validation, every referenced column in `components` must exist in `duckdb_result_summary.columns`, and deterministic heuristic assertions must pass (e.g., `KPIGrid` requires `row_count == 1`; `TimeSeriesChart` requires `x_column` to be `DATE`/`TIMESTAMP` or sequential period).

#### Step 3: Native `bfloat16` Supervised Fine-Tuning (SFT) on Modal (`A100-80GB` / `H100`)
When training 1.2B–3B models on Modal (`A100-80GB` or `H100-80GB`), **do not use Unsloth or 4-bit QLoRA (`nf4`)**:
* **Why Avoid 4-Bit QLoRA & Unsloth on Sub-3B Models**:
  1. **No VRAM Constraint on Modal**: Unsloth and 4-bit QLoRA were designed to squeeze 7B–70B models onto 16 GB consumer GPUs. A 1.5B–3B model in native `bfloat16` takes only **3–6 GB of VRAM** for weights. Even **100% Full Fine-Tuning (FFT)** with `AdamW` states, gradients, and activations consumes only **22–38 GB VRAM**—less than half of a single Modal `A100-80GB` or `H100`.
  2. **Avoiding Sub-3B Underfitting**: Unlike 14B+ models, 1.5B–3B models have tightly packed representations. Low-rank 4-bit QLoRA (`r=16`) introduces quantization noise during backward passes and frequently underfits when asked to learn both complex DuckDB SQL syntax and multi-component UI JSON schemas simultaneously.
  3. **Clean Modal Dependency Stack**: Standard Hugging Face [`transformers`](https://huggingface.co/docs/transformers) + [`trl` (`SFTTrainer`)](https://huggingface.co/docs/trl/en/sft_trainer) + [`flash-attn`](https://github.com/Dao-AILab/flash-attention) + [`liger-kernel`](https://github.com/linkedin/Liger-Kernel) runs natively on Modal without custom Triton monkey-patching issues across Qwen and Liquid LFM architectures, aligning directly with your existing `training/modal_*.py` infrastructure.

* **Two Recommended Modal Training Regimes (Compare Both in Your Harness)**:
  1. **Regime A — Native `bfloat16` Full Fine-Tuning (FFT) [Primary Recommendation for 1.2B–1.7B]**:
     * Updates **100% of model parameters** directly in `bf16` (zero adapter merge step, zero quantization mismatch, maximum capacity to internalize DuckDB dialect and UI schemas).
     * **Hyperparameters**: `learning_rate = 2e-5` (or `1.5e-5` for 3B), cosine decay with `min_lr_ratio = 0.1`, `warmup_ratio = 0.05`, `weight_decay = 0.05`, `max_grad_norm = 1.0`, `neftune_noise_alpha = 5.0` (prevents overfitting on synthetic phrasing), 2–3 epochs, effective batch size `32` (`per_device_train_batch_size = 8`, `gradient_accumulation_steps = 4`).
     * **Selective Layer Option ([Spectrum](https://github.com/cognitivecomputations/spectrum))**: If full weight updates slightly overfit on 3,000 examples, freeze the bottom 50% of low-SNR layers and full-fine-tune the top 50% high-SNR attention/MLP layers.
  2. **Regime B — Native `bfloat16` High-Rank DoRA / LoRA (`r = 64` or `128`) [Primary Recommendation for 3B]**:
     * Uses standard Hugging Face `peft` (`use_dora=True`, `r=64`, `lora_alpha=128`, `lora_dropout=0.05`) on top of an unquantized `bf16` base model, updating ~4–6% of parameters across all linear and short-convolution layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`/`out_proj`, `in_proj`, `gate_proj`/`w1`, `up_proj`/`w2`, `down_proj`/`w3`).
     * **Hyperparameters**: `learning_rate = 1e-4`, cosine scheduler, 3 epochs, effective batch size `16`.
* **Multi-Turn Completion-Only Loss Masking (`DataCollatorForCompletionOnlyLM` / `assistant_only_loss=True`)**:
  * Compute cross-entropy loss **exclusively** on valid assistant `<tool_call>` tokens (`Hop 1` and `Hop 2`). Mask all `system` (DDL), `user`, `tool` (`duckdb_result_summary` / `duckdb_execution_error`), and intentionally erroneous Split B Turn 1 assistant tokens (`labels = -100`).

#### Step 4: Execution-Guided Alignment on Modal (GRPO / DPO Pass)
Because GBNF already guarantees 100% syntactic JSON schema validity at inference time, running a 1-epoch [TRL `GRPOTrainer`](https://huggingface.co/docs/trl/main/en/grpo_trainer) or `DPOTrainer` job on a Modal `H100` / `A100-80GB` (~15 minutes) is the key unlock that pushes a 1.5B–3B model to 14B-class reliability:
* Sample `G = 4` trajectories per prompt from the SFT checkpoint at `temperature = 0.7` (without dynamic column GBNF during sampling so the model is penalized if it attempts to hallucinate columns).
* Score each completion using a deterministic multi-objective reward script (`reward_fn.py`):
  * **Hop 1 SQL Execution & Result Match (`+1.5` / `-1.0`)**:
    * `-1.0` if DuckDB throws a syntax/binder error or times out.
    * `+0.5` if SQL executes cleanly (`status == "ok"`), plus `+1.0` if the returned row set matches the gold reference SQL (`execution_match` from `nl_query/eval.py`).
  * **Hop 2 Column Binding Integrity (`+0.5` / `-1.0`)**:
    * `+0.5` if every column referenced in `render_workspace_ui` exists in the executed query's output schema; `-1.0` for any missing column binding.
  * **Hop 2 Semantic Visualization Fit (`+1.0` / `-0.5`)**:
    * `+1.0` if component selection matches data shape rules (e.g., `KPIGrid` used only when `row_count == 1` and numeric columns exist; `TimeSeriesChart` used only when `row_count >= 2` and `x_column` is a `DATE`/`TIMESTAMP`/period column; `CategoryBarChart` used when `2 <= distinct_count <= 25`; `DataTable` included when `row_count > 10` or `columns > 3`).
    * `-0.5` for anti-patterns (e.g., plotting a `VARCHAR` column on `y_columns`, rendering a `TimeSeriesChart` for a 1-row scalar result, or emitting duplicate chart types).

#### Step 5: High-Bitrate (`Q8_0` / `Q6_K`) + `imatrix` GGUF Quantization & Holdout Benchmarking
A critical mistake with 1.5B–3B models is applying the same aggressive 4-bit (`Q4_K_M`) quantization used on 14B models (`training/modal_export_gguf.py`). While a 14B model tolerates 4-bit quantization with negligible loss, **sub-3B models suffer noticeable degradation on exact SQL column identifiers and DuckDB function signatures at 4-bit**.
* **Why You Don't Need 4-Bit on 1.5B–3B Models**:
  * Because the parameter count is already small, **8-bit (`Q8_0`) and 6-bit (`Q6_K`) GGUF files are already compact enough (`1.6–2.4 GB`) to fit comfortably in 8–16 GB RAM** while preserving `99.5%+` of the `bf16` fine-tuned model's perplexity and SQL recall:
    1. **For 1.2B–1.7B Models → Ship `Q8_0` (`~1.3–1.8 GB`)**: Near-lossless vs. `bf16` weights and extremely fast on Apple Silicon Metal and AVX2/CUDA.
    2. **For 3B Models → Ship `Q6_K` or `Q5_K_M` Calibrated with `llama-imatrix` (`~2.1–2.4 GB`)**: Run `llama-imatrix` over the `f16.gguf` using a 200-example calibration dataset (`calibration_sql_genui.txt`) containing real DDL schemas, DuckDB SQL queries, and `render_workspace_ui` JSON payloads before quantizing.
* **200-Prompt Holdout Evaluation Suite (Expanding `nl_query/eval.py`)**:
  Evaluate on 200 held-out multi-turn test cases across seen and unseen schemas against four release gates:
  1. **Hop 1 First-Pass Execution Match (EX@1)**: Target `>= 90%` exact result-set match against gold SQL on the first attempt.
  2. **Hop 1 Self-Healing Execution Match (EX@3)**: Target `>= 96%` result-set match allowing up to 2 in-process DuckDB error-recovery retries.
  3. **Hop 2 UI Schema & Semantic Binding Accuracy**: Target `100%` valid component JSON (guaranteed by dynamic Hop 2 GBNF + Zod) and `>= 94%` semantic chart-suitability score.
  4. **End-to-End Interactive Latency**: Target `< 800ms` total LLM compute time (Hop 1 generation + DuckDB execution + KV-cached Hop 2 generation) on Apple Silicon (M1–M4) or modern desktop GPUs.

### 4.4 Modal GPU Training & Export Compute Requirements

| Modal Workload | Toolchain & Precision | Modal GPU Target | Wall-Clock Time (3,000 Trajectories, 3 Epochs) | Approximate Modal Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Synthetic Dataset Generation** | `vLLM` (`Qwen2.5-72B-Instruct-AWQ`) + Seeded DuckDB Validator | `1x A100-80GB` or `1x H100` | ~35–50 minutes | ~$2.50 – $4.00 |
| **1.5B–3B SFT (Full Fine-Tune or `r=64` DoRA)** | `transformers` + `trl` + `FlashAttention-2` + `Liger-Kernel` (`bf16`) | `1x A100-80GB` or `1x H100` | ~8–15 minutes | ~$0.60 – $1.20 |
| **Execution-Guided GRPO Alignment** | `TRL GRPOTrainer` (`bf16`) + In-Process DuckDB Reward | `1x H100` or `1x A100-80GB` | ~15–25 minutes | ~$1.00 – $2.00 |
| **Calibrated GGUF Export (`Q8_0` / `Q6_K`)** | `llama.cpp` (`convert_hf_to_gguf.py` + `llama-imatrix` + `llama-quantize`) | `1x A100-40GB/80GB` or High-CPU | ~6–10 minutes | ~$0.30 – $0.60 |

### 4.5 Modal Training Runbook & Script Architecture (`training/` Implementation Plan)

To ensure all four small-model recommendations and the operational lessons from `hackathonDocs/TRAINING_PLAYBOOK.md` are enforced on every training run, the `training/` and `nl_query/` pipeline is structured into five modular scripts:

| Script / Module | Role in the Training & Evaluation Process | Core Recommendations Enforced |
| :--- | :--- | :--- |
| `training/schema_pruner.py` | Deterministic BM25 + foreign-key graph table selector (`select_top_k_tables(question, schema, k=5)`). Shared between dataset synthesis, `eval.py`, and ported to Rust. | **Rec #3**: Keeps DDL prompt context to 4–6 relevant tables (<800 tokens), eliminating sub-3B attention dilution. |
| `training/gbnf_compiler.py` | Compiles canonical Zod/JSON tool schemas into `hop1_sql.gbnf` and dynamically generates `hop2_ui.gbnf` with exact DuckDB output column enums (`compile_hop2_gbnf(columns)`). | **Rec #4**: Guarantees 100% valid JSON tool calls and prevents Hop 2 column/component hallucination. |
| `training/modal_generate.py` | Runs `Qwen2.5-72B-Instruct-AWQ` on Modal `A100-80GB` against **seeded DuckDB warehouses**, injects 4–6 pruned tables (gold + hard-negative distractors), harvests 15% Split B `BinderError` self-healing turns, and validates Hop 2 UI calls. | **Rec #3 & #4**: Realistic `duckdb_result_summary` stats + explicit multi-turn error-recovery training data. |
| `training/modal_train_slm.py` | Runs native `bfloat16` **Full Fine-Tuning (FFT)** (for 1.2B–1.7B) or **`r=64` DoRA** (for 3B) + optional 1-epoch `GRPOTrainer` on Modal `A100-80GB`/`H100` using pure `transformers` + `trl` + `flash-attn` + `liger-kernel` (no Unsloth, no 4-bit QLoRA). | **Rec #1**: Full `bf16` gradient capacity without 4-bit quantization noise; masks loss on DDL, tool outputs, and Split B error turns. |
| `training/modal_export_gguf.py` | Exports `f16.gguf`, runs `llama-imatrix` over 200 calibration prompts (`calibration_sql_genui.txt`), and quantizes to **`Q8_0`** (1.2B–1.7B) or **`Q6_K`** (3B) in an isolated Modal container. | **Rec #2**: Preserves 99.5%+ of `bf16` SQL column accuracy in a ~1.6–2.3 GB desktop GGUF artifact. |

#### Operational Guardrails for Modal Training Runs (From `TRAINING_PLAYBOOK.md`)
1. **Fire-and-Forget via `modal deploy` + `.spawn()`**: Never use `modal run` for dataset generation, SFT, or GRPO jobs lasting >60 seconds (local terminal disconnects cancel active runs). Always deploy persistent Modal apps (`modal deploy training/modal_train_slm.py`) and trigger runs via Python `modal.Function.from_name(...).spawn()`.
2. **Bypass Trainer Pickle Crashes**: Configure `SFTConfig(save_strategy="no", bf16=True, assistant_only_loss=True)` and save final weights manually via `model.save_pretrained()` and `tokenizer.save_pretrained()` onto the mounted Modal volume (`/vol/checkpoints/<run_id>`), followed by `shutil.move()` (never `os.rename()` across container mount points) and `volume.commit()`.
3. **Isolated Container for Merge & `imatrix` GGUF Quantization**: Always invoke `export_gguf.remote()` in a fresh container rather than sharing GPU memory with the training process. If using Regime A (`bf16` Full Fine-Tuning), skip `PeftModel.merge_and_unload()` entirely and convert the saved `bf16` checkpoint directly to `f16.gguf` → `llama-imatrix` → `Q8_0` / `Q6_K`.

## 5. Immediate Next Steps to Validate the Prototype

1. **Freeze the Canonical Zod & GBNF Tool Contracts (`training/gbnf_compiler.py`)**: Define the exact schemas for `execute_duckdb_query`, `duckdb_result_summary`, and `render_workspace_ui` (`KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, `FilterBar`) and implement dynamic column-enum compilation for `hop2_ui.gbnf`.
2. **Build the Top-K Schema Pruner & Benchmark Zero-Shot Sub-3B Models**: Implement `training/schema_pruner.py` (`k=5` tables) and extend `nl_query/eval.py` to test zero-shot `Qwen2.5-Coder-1.5B/3B` and `LFM2.5-1.2B` (`Q8_0` GGUF) with GBNF constraints and 2-retry DuckDB self-healing on 50 prompts.
3. **Run the Upgraded Modal Training Pipeline**:
   * Execute `training/modal_generate.py` against seeded DuckDB warehouses (`analytics.duckdb` + seeded finance tables) to produce 3,000 pruned 2-hop + Split B error-recovery trajectories.
   * Deploy and spawn `training/modal_train_slm.py` on Modal `A100-80GB`/`H100` in native `bf16` (Full Fine-Tuning for 1.5B/1.7B, `r=64` DoRA for 3B).
   * Export calibrated `Q8_0` (1.5B) and `Q6_K` + `imatrix` (3B) GGUF models via `training/modal_export_gguf.py` and verify against the 200-prompt holdout gate.
4. **Stand Up the Minimal `Wry` + `DuckDB` + `arrow://` Spike**: Build a single-window Rust binary that executes one DuckDB query, supports parameterized `FilterBar` CTE wrapping, and streams an Apache Arrow table to a React/Svelte chart over `wry::WebViewBuilder::with_custom_protocol`.
