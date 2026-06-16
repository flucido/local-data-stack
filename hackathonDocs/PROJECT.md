# Kasualdad LFED — Project Knowledge Base

> **Last updated:** 2026-06-12 (Session 5 — ZeroGPU transformers backend)
> **Target:** HF Build Small Hackathon — "Backyard AI" chapter
> **Space:** https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED
> **Remote:** `git@hf.co:spaces/build-small-hackathon/Kasualdad_LFED` (remote name: `space`)

---

## ⚠️ Current State (read this first)

The inference backend was **swapped on `main`** (2026-06-12): llama.cpp could
not work on ZeroGPU (PyTorch-only CUDA emulation — see `DEPLOY.md`), so the
Space now runs **transformers + PEFT**: pre-quantized 4-bit base
(`unsloth/qwen2.5-coder-14b-instruct-bnb-4bit`) + LoRA adapter
(`build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora`) — the exact QLoRA
training configuration.

- **`main`** = Space demo (transformers, ZeroGPU, streaming UI, deterministic Parquet seed via LFS)
- **`local-llamacpp-v1` (tag) / `product` (branch, worktree `.worktrees/product`)** = llama.cpp + GGUF local-first base — the foundation for the real product
- Sections below marked **[HISTORICAL — llama.cpp]** describe the old backend;
  they remain accurate **for the `product` branch only**.
- Next feature: `docs/SPEC_query-history-dashboards.md` (draft, not built)

---

## What It Does

A Gradio app that lets school district admins ask plain-English questions about student data. A fine-tuned LLM (Qwen2.5-Coder-14B, QLoRA on 27,859 NL→SQL pairs) generates DuckDB SQL, which is validated and executed on in-memory seed data. **Local-first by design** — on the `product` branch nothing leaves the machine; the Space demo runs the same fine-tune on ZeroGPU.

---

## Architecture & Data Flow

```
User types question
  ↓
app.py  →  handle_query()  [generator; @spaces.GPU(duration=30) on ZeroGPU]
  ↓
model_inference.py  →  build_prompt() + TransformersLLM (bnb-4bit base + LoRA)
  ↓  streamed SQL tokens (llama.cpp-compatible response schema)
data_engine.py  →  extract_sql() → validate_sql() → execute_safe()
  ↓  pandas DataFrame
app.py  →  streams SQL, then renders table in Gradio UI
```

**Key design rule:** `app.py` is a thin controller. All logic lives in the three engine modules.

---

## File Map

| File | Purpose | Lines |
|---|---|---|
| `app.py` | Gradio UI (ResearchMono theme), streaming `handle_query` generator, `@spaces.GPU(duration=30)`, Parquet bootstrap (all 5 files) | ~290 |
| `model_inference.py` | `TransformersLLM` wrapper (bnb-4bit base + LoRA, llama.cpp-compatible call schema), SQL generation + streaming | ~270 |
| `data_engine.py` | DuckDB lifecycle, Parquet loading (5 tables), SQL extraction/validation/execution | ~280 |
| `prompts.py` | System prompt, 5-table schema docs, 4 few-shot examples, prompt assembler | ~190 |
| `data/generate_seed.py` | Deterministic generator: 2,900 students across 5 tables (re-seeds RNG per call) | ~430 |
| `data/export_parquet.py` | One-shot script: seed → 5 Parquet files | ~70 |
| `data/*.parquet` | 5 committed seed files via LFS (~260 KB total, byte-deterministic) | — |
| `requirements.txt` | Pinned Python deps (see below) | 9 lines |
| `README.md` | Public Space README | ~280 |
| `docs/HANDOFF.md` | Developer session handoff doc | ~190 |
| `docs/PLAN.md` | Original build plan | ~170 |
| `tests/` | pytest suite (81 tests: execution guard, data engine, model inference) | 4 files |
| `modal_train/` | Modal fine-tuning pipeline (synthetic data, Unsloth QLoRA, GGUF export) | 5 files |

---

## Model & Inference

### Active Model (`main` — Space)

- **Base:** `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit` (pre-quantized NF4, ~10 GB download)
- **Adapter:** `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora` (551 MB, QLoRA r=32, α=32)
- **Loaded via:** transformers `AutoModelForCausalLM` + `PeftModel.from_pretrained(..., torch_device="cpu")`
  (the `torch_device="cpu"` is required on ZeroGPU — adapter loading straight to cuda fails at startup)
- **Env overrides:** `LFED_BASE_MODEL`, `LFED_ADAPTER_REPO`

### Active Model (`product` — local) [HISTORICAL — llama.cpp]

- **Repo:** `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-gguf` (Q4_K_M, ~9 GB; 7B fallback exists)
- llama.cpp via `llama-cpp-python`, Metal on macOS

### Inference Config (`main`)

| Parameter | Value | Note |
|---|---|---|
| `max_tokens` | 192 | Outputs run ~140-170 chars |
| `temperature` | 0.0 | Deterministic (greedy) |
| `stop` | `\n\n`, `Question:`, `User:`, `<\|im_end\|>`, `<\|im_start\|>` | Applied post-hoc + streaming truncation |
| Few-shots | 4 | Trimmed from 7 to cut bnb-4bit prefill cost |
| `spaces.GPU` | `duration=30` | Shorter duration = ZeroGPU queue priority |
| Generation time | ~5 s/query | Rest of latency = ZeroGPU queue + weight restore |

### Thread Safety

`model_inference.py` caches the model in a module-level `_llm` global with a `threading.Lock` (double-check pattern). `generate_sql()` auto-loads if `llm=None`.

---

## Zero GPU / HF Space Configuration

### Space Identity
- **URL:** `https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED`
- **SDK:** Gradio 6.16.0
- **Python:** 3.12
- **Hardware:** Zero GPU (NVIDIA RTX Pro 6000 Blackwell, half — 48 GB VRAM)
- **Git remote:** `space` → `https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED`

### Zero GPU Architecture

Zero GPU uses **CUDA emulation** at module level and **real GPU** inside `@spaces.GPU` functions. This means:
- Model loads with `n_gpu_layers=-1` at startup (module level, emulated CUDA)
- Inference runs inside `@spaces.GPU` decorated `handle_query()` (real GPU)
- Zero GPU transparently switches between emulated and real CUDA contexts

### `@spaces.GPU` Decorator

`app.py:37` — `handle_query()` is the only decorated function. Required for Zero GPU to recognize the Space as GPU-enabled.

### Startup Sequence (app.py:16-30)

1. Print banner
2. **Ensure Parquet seed files exist** — all **5** files (`enrollment`, `attendance`, `students`, `discipline`, `grades`) must be present in `/data/` or `data/`; they are committed via LFS (byte-deterministic). If any are missing, regenerate via `export_parquet.py`. *Gotcha fixed 2026-06-12: with files missing, `seed_database()` silently fell back to the Python generator per request, producing different data on every query.*
3. Load model (`load_model()`) — downloads base + adapter from HF Hub if not cached
4. Launch Gradio UI

---

## CUDA Dependency Story (Full Debugging History) [HISTORICAL — llama.cpp]

> This entire section applies to the llama.cpp backend (`product` branch).
> On `main`, llama.cpp and the ctypes preloading were removed entirely —
> ZeroGPU never supported non-PyTorch CUDA, which is why the backend changed.

### Problem
`llama-cpp-python` installed with CUDA 12.1 wheel (`--extra-index-url .../cu121`). At import time, `libllama.so` needs multiple CUDA shared libraries (`libcudart.so.12`, `libcublas.so.12`, `libcublasLt.so.12`, etc.), but they aren't on the system linker path in the HF Space container.

### Failed Attempt #1 — `LD_LIBRARY_PATH` via `os.environ`
**Why it failed:** The C dynamic linker (`ld.so`) reads `LD_LIBRARY_PATH` once at process start. Setting `os.environ["LD_LIBRARY_PATH"]` in Python at runtime has zero effect on `dlopen()`.

### Failed Attempt #2 — Load only `libcudart.so.12`
**Why it failed:** `libllama.so` also needs `libcublas.so.12`, `libcublasLt.so.12`, and other CUDA libs. Loading just `libcudart` got us past the first error but hit the next missing library.

### Working Solution — Bulk ctypes preload
`model_inference.py:20-78`

```python
import ctypes

def _preload_dir(lib_dir):
    """Preload every lib*.so* in a directory with RTLD_GLOBAL."""
    for f in sorted(os.listdir(lib_dir)):
        if f.startswith("lib") and ".so" in f:
            ctypes.CDLL(os.path.join(lib_dir, f), mode=ctypes.RTLD_GLOBAL)
```

**Why it works:** `ctypes.CDLL(full_path, mode=RTLD_GLOBAL)` calls `dlopen()` with the full path + `RTLD_GLOBAL` flag. This loads the library into the process and registers it under its SONAME. When `libllama.so` is subsequently `dlopen()`'d, the linker finds all CUDA dependencies already resident.

**Search order:**
1. System CUDA: `/usr/local/cuda/lib64`, `/usr/local/cuda-12.1/lib64`, `/usr/local/cuda-12.4/lib64`
2. Pip packages: iterate `sys.path`, find `nvidia/*/lib/` directories, preload all `.so` files

### Required CUDA Pip Packages

| Package | Version | Provides |
|---|---|---|
| `nvidia-cuda-runtime-cu12` | 12.1.105 | `libcudart.so.12` |
| `nvidia-cublas-cu12` | 12.1.3.1 | `libcublas.so.12`, `libcublasLt.so.12` |
| `nvidia-cusparse-cu12` | 12.1.0.106 | `libcusparse.so.12` |

These are in `requirements.txt`. On the HF Space, the bulk preload picked up **39 total CUDA shared libraries** from the transitive dependencies of these packages. [HISTORICAL — the `main` branch no longer includes these packages.]

### Import Guard [HISTORICAL — llama.cpp]

`model_inference.py:81-91` — If the `from llama_cpp import Llama` still fails (truly missing CUDA), a `RuntimeError` with a clear diagnostic is raised:

```
Failed to load llama-cpp-python — CUDA runtime not found.
If this is a CPU-only machine, install the CPU wheel:
  pip uninstall llama-cpp-python -y && pip install llama-cpp-python
```

> This code was removed on `main` in 2026-06-12; the import guard now lives
> in `LOAD_SKIP_MODEL` env check and `TransformersLLM.__init__` error handling.

---

## UI Design System [HISTORICAL — Old design replaced 2026-06-10]

> The palette, fonts, and CSS overrides below were replaced by **ResearchMono**
> (`gr.themes.Soft` + IBM Plex Sans/Mono + `#4589FF` accent). The new approach
> uses Gradio's native theming; the aggressive CSS overrides below are gone.
> This section is kept for the Off-Brand badge documentation only.

### Old Palette (replaced)

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#f1f5f9` (slate-100) | Page background |
| `--surface` | `#ffffff` | Cards, inputs, code blocks, tables |
| `--surface-alt` | `#f8fafc` (slate-50) | Table headers |
| `--border` | `#e2e8f0` (slate-200) | All borders |
| `--text` | `#1e293b` (slate-800) | Primary body text |
| `--text-muted` | `#64748b` (slate-500) | Secondary text, labels |
| `--action` | `#4f46e5` (indigo-600) | Primary CTA buttons |
| `--action-hover` | `#4338ca` (indigo-700) | Button hover state |
| `--error` | `#b91c1c` (red-700) | Error messages |
| `--success` | `#059669` (emerald-600) | Success messages |
| `--radius` | `12px` | All containers, inputs |
| `--radius-lg` | `20px` | (defined but not heavily used) |
| `--transition` | `120ms ease-out` | Hover/focus transitions |

### Old Fonts (replaced)
- **Headings:** Cormorant Garamond (serif) — `--font-display`
- **Body/UI:** Atkinson Hyperlegible (sans) — `--font-ui`
- **Code:** JetBrains Mono — `--font-mono`

All were loaded via Google Fonts in `HEAD_HTML` (`app.py:345`). Now uses IBM Plex Sans + IBM Plex Mono via `gr.themes.Soft`.font / `.font_mono`.

### Old CSS Override Strategy (replaced by gr.themes.Soft)
`app.py:77-82` — A "nuke block" strips Gradio's dark-theme defaults before our rules apply:
```css
.gr-textbox, .gr-code, .gr-dataframe, .gr-accordion {
    background: transparent !important;
    border-color: transparent !important;
}
```

The CSS uses aggressive descendant selectors (`> div > div`, `[data-testid]`) because Gradio nests components in multiple wrapper divs.

### Design Evolution
1. **Original:** Linear/Vercel inspired — teal accent (`#14b8a6`), Inter font, CSS overrides against Gradio defaults
2. **WellFull Collective:** Warm terracotta + sage palette — rejected (looked "bad" for a data tool)
3. **Slate + Indigo:** Cool professional palette with the WellFull structure (fonts, radii, spacing)
4. **Current (ResearchMono):** `gr.themes.Soft` + IBM Plex Sans/Mono + `#4589FF` accent — Gradio native theming with no CSS override hacks

---

## Data Engine & Parquet Optimization

### Per-Request Lifecycle
`data_engine.py:create_session()` → `get_connection()` + `seed_database()`

Each query creates a **fresh in-memory DuckDB** connection. This ensures:
- Thread safety (no shared state between requests)
- Query isolation (can't affect other requests)
- Clean state (no stale data)

### Seeding Priority
`data_engine.py:seed_database()` [data_engine.py:62-96]

1. **Parquet files** (fastest — ~260 KB, single-digit ms). Requires **all 5**
   tables (`enrollment`, `attendance`, `students`, `discipline`, `grades`) in
   `/data/` (Space persistent storage) or `data/` (local dev, committed via LFS).
   Loaded via DuckDB `read_parquet()` → `CREATE TABLE ... AS SELECT *`.
   *If any file is missing the whole path is skipped — this caused the
   nondeterministic-results bug fixed 2026-06-12.*
2. **`data/seed.sql`** (custom overrides)
3. **Python generator** `data/generate_seed.py` (slow fallback — ~2,900 students, ~11,600 attendance rows)

### Parquet Bootstrap
`app.py:22-29` — On startup, if no Parquet files are found in any of the search dirs, `export_parquet.py` is called to generate them. On the Space, they go to `/data/` which persists across restarts.

### SQL Safety Pipeline
`data_engine.py:execute_safe()` [data_engine.py:235-260]

1. `extract_sql()` — Parse JSON envelope → ```sql``` block → raw fallback
2. `validate_sql()` — Forbidden token check (DROP, DELETE, INSERT, UPDATE, etc.) + schema-aware `EXPLAIN` validation
3. Wrap: `SELECT * FROM (<user_query>) AS _safe LIMIT 1000`
4. Execute directly on DuckDB
5. Return `(cleaned_sql, DataFrame)`

### Forbidden Tokens
`data_engine.py:22-25` — `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `CREATE`, `ATTACH`, `DETACH`, `PRAGMA`

---

## Database Schema

### `enrollment`

| Column | Type | Description |
|---|---|---|
| `school_year` | VARCHAR | School year, format `'YYYY-YYYY'` |
| `school_name` | VARCHAR | One of 5 schools |
| `grade_level` | INTEGER | Grade level (K=0 through 12) |
| `student_count` | INTEGER | Students enrolled in that grade/year/school |

### `attendance`

| Column | Type | Description |
|---|---|---|
| `student_id` | INTEGER | Unique student identifier |
| `school_name` | VARCHAR | School the student attends |
| `school_year` | VARCHAR | School year, format `'YYYY-YYYY'` |
| `absence_count` | INTEGER | Total absences for that year |
| `is_chronically_absent` | BOOLEAN | TRUE if missed ≥10% of school days |

### Schools

| School | Grades | Base Enrollment |
|---|---|---|
| Lincoln Elementary | K–5 | 520 |
| Washington Middle | 6–8 | 480 |
| Jefferson High | 9–12 | 900 |
| Roosevelt Academy | K–8 | 380 |
| Kennedy Prep | 6–12 | 620 |

### Seed Data Stats
- **Students:** 2,900
- **Chronic absenteeism rate:** 15% (435 students)
- **Enrollment rows:** 116 (5 schools × 4 years × variable grades)
- **Attendance rows:** 11,600 (2,900 students × 4 years)
- **School years:** 2021-2022, 2022-2023, 2023-2024, 2024-2025
- **YOY growth:** 3% per year with ±15% random grade-size variance
- **Reproducible:** `random.seed(42)` in `generate_seed.py`

---

## Prompt Engineering

`prompts.py` assembles the full LLM prompt:

### Structure
```
SYSTEM_PROMPT (rules, constraints, output format)
  ↓
Schema documentation (table + column list)
  ↓
Few-shot examples (4 question→SQL pairs)
  ↓
User question
  ↓
"SQL:"
```

### System Prompt Rules
`prompts.py:SYSTEM_PROMPT` [prompts.py:9-18]
1. Only SELECT statements
2. Exact table/column names from schema
3. Proper DuckDB syntax (VARCHAR → single quotes, BOOLEAN → TRUE/FALSE)
4. Use column aliases for aggregations
5. Join on logical columns
6. Make reasonable assumptions if ambiguous
7. Output ONLY the ```sql``` block, no explanation

### Few-Shot Examples
`prompts.py:FEW_SHOT_EXAMPLES` [prompts.py:56-76]

| Question | SQL pattern |
|---|---|
| "How many chronically absent in 2023-2024?" | `COUNT(*)` with `WHERE ... AND is_chronically_absent = TRUE` |
| "Show enrollment per school sorted" | `SUM(student_count) GROUP BY school_name ORDER BY ... DESC` |
| "What percentage at Lincoln Elementary?" | `COUNT(CASE WHEN ...) * 100.0 / COUNT(*)` |
| "Enrollment trend since 2021" | `GROUP BY school_year ORDER BY school_year` |

---

## Fine-Tuning Pipeline (Modal)

### Location: `modal_train/` — **v2 (current)**

| Script | Purpose |
|---|---|
| `generate_synthetic_v2.py` + `modal_generate.py` + `augment_gretel.py` + `rephrase_pairs.py` | Builds the 27,859-pair dataset (`train_final_v2.jsonl`) |
| `train_v2.py` | Unsloth QLoRA on Qwen2.5-Coder-14B (r=32, α=32, 4-bit, 2 epochs, lr=1e-4, A10G) |
| `export_gguf_v2.py` | Merges LoRA → GGUF Q4_K_M → pushes to HF Hub |
| `modal_train_v2.py` | Modal orchestration (`modal.App("kasualdad-lfed-train-v2")`) |
| v1 scripts (`train.py`, `export_gguf.py`, `modal_app.py`) | [HISTORICAL] 7B run, 1,289 pairs |

### How to Run
```bash
modal secret create huggingface-secret HF_TOKEN=<token>
modal run modal_train/modal_train_v2.py
```

### Artifacts (Status: ✅ trained 2026-06-10)
| Artifact | Location |
|---|---|
| LoRA adapter | `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora` (HF Hub) + Modal volume `lfed-training-data:/lora-adapter-v2` |
| GGUF Q4_K_M | `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-gguf` (HF Hub) |
| Merged fp16 | ⚠️ Not persisted (existed only in an ephemeral Modal container). Re-merge from base + adapter if ever needed. |

---

## Dependencies

### Python (`requirements.txt`, `main` branch)

| Package | Why |
|---|---|
| `gradio` >= 6.15 | Web UI |
| `duckdb` 1.5.3 | In-memory SQL engine |
| `torch` / `transformers` / `peft` / `bitsandbytes` / `accelerate` | Model inference (bnb-4bit base + LoRA) |
| `huggingface_hub` + `hf_transfer` | Fast model download |
| `spaces` | `@spaces.GPU` decorator for ZeroGPU |

The `product` branch instead pins `llama-cpp-python` (no torch stack needed).

---

## Hackathon Badges

| Badge | Status | Implementation |
|---|---|---|
| **Off the Grid** | ✅ | `product` branch: llama.cpp + local GGUF, no API calls. `main`/Space: same fine-tune on ZeroGPU (transformers). |
| **Well-Tuned** | ✅ | Fine-tuned Qwen2.5-Coder-14B, QLoRA r=32 on 27,859 NL→SQL pairs (Modal A10G). |
| **Llama Champion** | ✅ | llama.cpp is the local-first inference backend (GGUF Q4_K_M, Metal, streaming). |
| **Off-Brand** | ✅ | Custom ResearchMono theme — IBM Plex Sans/Mono, `#4589FF` accent, `gr.themes.Soft`. |

---

## Gotchas & Pitfalls

### 1. `LD_LIBRARY_PATH` doesn't work at Python runtime [HISTORICAL — llama.cpp]
The dynamic linker caches it at process start. Use `ctypes.CDLL(path, mode=RTLD_GLOBAL)` to preload libraries instead.

### 2. Zero GPU architecture [HISTORICAL — llama.cpp]
On the old llama.cpp backend: load models with GPU layers at startup (module level), not lazily inside `@spaces.GPU` functions. The docs explicitly say lazy loading is "significantly less efficient." Note: this advice only applies to the llama.cpp path — the current transformers path (main) loads at startup via PyTorch `device_map="auto"`.

### 3. ZeroGPU = PyTorch-only CUDA [2026-06-12]
ZeroGPU's `spaces.GPU` decorator works through a PyTorch patching layer — non-PyTorch CUDA libraries (llama.cpp's `libllama.so`, `libggml-cuda.so`) cannot benefit from it. The fix was to drop llama.cpp on the Space and use transformers + PEFT + bnb-4bit instead, which is the exact configuration the model was QLoRA-trained in. The `product` branch keeps llama.cpp for local Mac/GPU use.

### 4. PEFT adapter loading straight to `cuda:0` fails on ZeroGPU [2026-06-12]
`PeftModel.from_pretrained()` defaults to loading adapter safetensors directly onto `cuda:0`, which ZeroGPU forbids at startup. Fix: `torch_device="cpu"` — CPU tensors copy into the model's emulated-CUDA LoRA layers via normal torch ops.

### 5. Parquet files committed via LFS [2026-06-12]
All 5 Parquet seed files are committed via git LFS (not force-added; the old `.gitignore` `data/*.parquet` rule was removed). They are byte-deterministic (verified by re-regenerating and comparing MD5). HF Spaces requires LFS for binary files >10 KB. Re-export with `python data/export_parquet.py` if the seed data generator changes.

### 6. Missing Parquet fallback = nondeterministic data per query [2026-06-12]
`seed_database()` requires all 5 Parquet files. If any are missing, it falls through to the Python generator, which advances the shared `random` RNG on each call → different data per query (the 1411 vs 1446 discipline rows bug). Fixed by committing all 5 files + re-seeding the RNG inside `generate_seed_data()` + requiring all 5 in the startup check.

---

## Quick Start

```bash
# Clone
cd Kasualdad_LFED

# Virtual env
python3.12 -m venv .venv && source .venv/bin/activate

# Install
pip install -r requirements.txt

# Generate Parquet seed files (first time only)
python data/export_parquet.py

# Run
python app.py
# → http://localhost:7860

# Tests
pytest tests/ -v

# Deploy
git push space main
```

---

## Git History (2026-06-12 session — backend swap + data fix)

```
3cf2ed0 fix: deterministic seed data — commit all 5 parquet files (LFS)
2eccdc1 perf: stream SQL to UI, trim few-shots 7→4, GPU duration 30s
e8c46ef fix: load LoRA adapter weights to CPU for ZeroGPU startup compat
de794a7 Switch inference to transformers + bnb-4bit + LoRA for ZeroGPU
```

### Prior sessions (Hackathon building + llama.cpp era)

```
53a83b7 Switch from Zero GPU to T4: remove Dockerfile, simplify theme
18b6a67 fix: remove --no-binary flag (OOM during build), use pre-built CUDA wheel
240383f Day 1 expanded schema: 5 tables, 14B fine-tuned model
9ae0db2 fix: add llama-cpp-python to requirements.txt, simplify Dockerfile
ebd632e fix: install CUDA llama-cpp-python BEFORE spaces, add verification step
0e9c140 perf: load seed data from Parquet instead of generating on every query
9bae1e9 fix: remove remaining fine-tuned model repo ID from HANDOFF.md
... (older commits — see git log for full history)
```

---

## Future Work

- [x] **Fine-tuning completed** — 14B model trained (27,859 pairs), GGUF + LoRA adapter published to HF Hub
- [x] **Swapped to fine-tuned model** — `main` uses transformers + LoRA on ZeroGPU; `product` uses llama.cpp + GGUF locally
- [x] **Streaming re-enabled** — `generate_sql_streaming()` wired into the UI; tokens appear in ~2-3 s
- [x] **Deterministic seed data** — all 5 Parquet files committed via LFS, byte-reproducible
- [ ] **Query history + comparisons** — see `docs/SPEC_query-history-dashboards.md` (spec drafted)
- [ ] **Dashboards** — Standard Board (`dashboards/standard.json`) + Ephemeral Scratch Board (same spec)
- [ ] **HF Space smoke test** — verify all 6 example queries return correct results after each deploy
- [ ] **Product branch development** — build the local-first features on `product` branch (`.worktrees/product`)
