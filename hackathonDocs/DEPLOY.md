# Kasualdad LFED — Deployment Troubleshooting & Resolution

> **⚠️ Historical document + final resolution.** Sections below describe the
> llama.cpp deployment attempts and a *proposed* T4 switch that was **not**
> taken. The actual resolution (stay on ZeroGPU, drop llama.cpp for
> transformers + LoRA) is documented at the end — see
> [Final Resolution](#final-resolution-implemented-stay-on-zerogpu-with-transformers--lora).

## What We're Trying to Accomplish

Deploy the Kasualdad LFED Space (a local-first education data analytics app) on Hugging Face Spaces with GPU acceleration. The app uses `llama-cpp-python` to run a fine-tuned Qwen2.5-Coder-14B GGUF model (Q4_K_M, ~9GB) for text-to-SQL generation.

**Stack:**
- Gradio 6.x UI with DuckDB backend
- llama-cpp-python (CUDA build) for LLM inference
- Fine-tuned model: `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-gguf`
- 5-table seed schema: enrollment, attendance, students, discipline, grades

## Code Architecture — Where Does the Model Run?

The model inference code is NOT a single file — it's split across four files with clear responsibilities:

### `model_inference.py` (293 lines) — The core LLM wrapper

| Lines | What It Does |
|-------|-------------|
| 29-73 | **CUDA preloading**: Uses `ctypes.CDLL(..., RTLD_GLOBAL)` to preload every `lib*.so*` from system CUDA dirs and pip-installed `nvidia-*-cuXX/lib` packages. Prints "🔧 Preloaded N CUDA shared libraries" on success. |
| 80 | **`from llama_cpp import Llama`** — This is the import that failed on Zero GPU because `llama-cpp-python` wasn't installed. Caught by `try/except (OSError, RuntimeError)` on lines 79-90. |
| 97-107 | **Model path resolution**: Cascade check — tries cached 14B GGUF → cached 7B GGUF → `/tmp/lfed-models/qwen/...` → downloads from HF Hub as last resort. |
| 109-116 | **Inference defaults**: `n_ctx=4096`, `n_threads=4` (Zero GPU) or `2` (local), `n_gpu_layers=-1` (all layers on GPU), `temperature=0.0`, `max_tokens=256`. |
| 138-184 | **`load_model()`**: Thread-safe lazy loader. Creates `Llama(model_path, n_gpu_layers=-1, ...)` instance. Cached globally in `_llm`. **Called at module level** by `app.py:41` before Gradio starts. |
| 194-233 | **`generate_sql()`**: Takes user question → builds prompt via `prompts.py` → runs `llm(prompt, max_tokens=256, stop=[...], temperature=0.0)` → returns raw SQL text. |
| 236-292 | **`generate_sql_streaming()`**: Token-by-token generator for Gradio `stream=True`. Accumulates text, checks for stop sequences, yields on each chunk. |

### `app.py` (277 lines) — Entry point & Gradio UI

| Lines | What It Does |
|-------|-------------|
| 13-17 | **GPU decorator**: Tries `import spaces; _gpu_decorator = spaces.GPU`. Falls back to no-op locally. |
| 19 | **`from model_inference import load_model, generate_sql`** — triggers ALL of `model_inference.py` module-level code, including CUDA preloading and the `llama_cpp` import attempt. |
| 41 | **`llm = load_model()`** — FIRES AT IMPORT TIME. The model loads before Gradio starts. If this fails, the Space crashes before showing any UI. |
| 57-85 | **`handle_query()`**: Decorated with `@_gpu_decorator`. Calls `generate_sql()` → validates SQL → runs on DuckDB → returns (sql_text, dataframe, status). |
| 167-274 | **Gradio UI**: `gr.Blocks` with `gr.themes.Soft` (IBM Plex fonts), two-column layout (input left, output right), 6 example query chips. |

### `prompts.py` — Prompt construction

| Lines | What It Does |
|-------|-------------|
| 11-101 | **`DEFAULT_SCHEMA`**: Schema documentation for all 5 tables (column names, types, descriptions). Injected into the system prompt. |
| 104-128 | **`FEW_SHOT_EXAMPLES`**: 7 question→SQL pairs for in-context learning. Includes cross-table JOIN examples (chronic absentee ELL students, GPA vs chronic absence, discipline by school). |
| ~160 | **`build_prompt()`**: Assembles Qwen2.5 chatml-format prompt: system message with schema + few-shots → user question → `<\|im_start\|>assistant` |

### `data_engine.py` — DuckDB backend

| Lines | What It Does |
|-------|-------------|
| 63-101 | **`seed_database()`**: Tries Parquet files first (fast), then `seed.sql`, then Python generator fallback. |
| ~120 | **`execute_safe()`**: Validates generated SQL (read-only, no DDL/DML), runs on a fresh per-request DuckDB instance, returns cleaned SQL + DataFrame. |

### Critical Dependency Chain

```
app.py (import at line 19)
  └─ model_inference.py (imports trigger at module level)
       ├─ ctypes CUDA preloading (lines 29-73)
       ├─ from llama_cpp import Llama (line 80) ← WAS FAILING
       └─ prompts.py (used by generate_sql())
  └─ data_engine.py (used by handle_query())

app.py (line 41)
  └─ llm = load_model()  ← GPU required here, blocks startup
```

**Key insight:** The model loads at import time (line 41), not lazily. This means:
1. If `llama-cpp-python` isn't installed → import fails immediately (Issue #1)
2. If CUDA isn't available → `Llama(n_gpu_layers=-1)` fails at startup
3. If the GGUF file isn't cached → downloads on startup (slow, but works)

**Current model:** `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-gguf` (Q4_K_M, ~9GB)
**Fallback model:** `build-small-hackathon/lfed-qwen2.5-coder-7b-sql-gguf` (Q4_K_M, ~4.5GB)

---

## Issue #1: `ModuleNotFoundError: No module named 'llama_cpp'`

**Symptom:** Runtime crash on Space startup.

```
File "/home/user/app/model_inference.py", line 80, in <module>
    from llama_cpp import Llama
ModuleNotFoundError: No module named 'llama_cpp'
```

**Root cause:** `llama-cpp-python` was NOT listed in `requirements.txt`. The Dockerfile tried to install it separately and then patch `requirements.txt` on the fly with `echo >>`, but HF Spaces reads the repo's `requirements.txt` directly — not the Dockerfile-modified version.

**Fix applied:** Added `llama-cpp-python` to `requirements.txt`.

**Commit:** `9ae0db2` — "fix: add llama-cpp-python to requirements.txt, simplify Dockerfile"

---

## Issue #2: Docker Build OOMKilled (exit code 137)

**Symptom:** Build failed with `exit code: 137. Reason: OOMKilled`.

**Root cause:** Dockerfile used `--no-binary llama-cpp-python` to force source compilation with `CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75"`. Compiling llama-cpp-python from source (C++ + CUDA) exhausted the build VM's memory.

**Fix applied:** Removed `--no-binary` flag to use pre-built CUDA wheels instead.

**Commit:** `18b6a67` — "fix: remove --no-binary flag (OOM during build), use pre-built CUDA wheel"

---

## Issue #3: Dockerfile Completely Ignored by HF Spaces Zero GPU

**Symptom:** Despite our custom Dockerfile (`FROM nvidia/cuda:12.1.0-devel-ubuntu22.04`), the build logs showed:

```
FROM docker.io/library/python:3.12.12
```

The Space was using HF's own managed build system, not our Dockerfile. Our `CMAKE_ARGS`, custom CUDA paths, and `--no-binary` flags were dead code.

**Root cause:** HF Spaces Zero GPU does NOT support custom Dockerfiles. It uses a managed Python 3.12.12 image with pinned PyTorch versions (2.8.0, 2.9.1, 2.10.0, 2.11.0) and CUDA 13 libraries. The Space hardware was `zero-a10g` (not `zero-gpu` as assumed).

**Additional finding:** The CUDA preloading code in `model_inference.py` looks for CUDA 12 paths (`/usr/local/cuda-12.1/lib64`, `/usr/local/cuda-12.4/lib64`), but Zero GPU uses CUDA 13 via pip packages (`nvidia-cublas-cu13`, `nvidia-cuda-runtime-cu13`). The fallback `sys.path` scanning catches these, but the Zero GPU "CUDA emulation" is PyTorch-only — non-PyTorch CUDA libraries (like llama.cpp's `libllama.so`) do not benefit from it.

**Proposed fix:** Switch from Zero GPU to a regular GPU Space (Nvidia T4 - small at $0.40/hr). Regular GPU Spaces provide full CUDA access and support custom Dockerfiles or the standard HF GPU base image.

---

## Issue #4: llama-cpp-python Source Build Hangs on HF Spaces

**Symptom:** Build logs show source compilation starting but never completing:

```
Building wheel for llama-cpp-python (pyproject.toml): started
Building wheel for llama-cpp-python (pyproject.toml): still running...
```

**Root cause:** This is a known issue on HF Spaces since the Debian 13 upgrade. The community recommendation is: **never compile llama-cpp-python inside a Space.** Use a pre-built wheel instead.

**Relevant discussion:** https://discuss.huggingface.co/t/using-llama-cpp-on-spaces/172216

---

## Final Proposed Solution: Switch to Regular GPU Space (T4)

### Why T4 instead of Zero GPU

| Factor | Zero GPU | T4 GPU Space |
|--------|----------|--------------|
| CUDA access | PyTorch-only emulation | Full native CUDA |
| Custom Dockerfile | Not supported | Supported |
| llama-cpp-python CUDA | Cannot use (non-PyTorch) | Works natively |
| Billing | Free (but broken for us) | $0.40/hr, billed by minute |
| Build time | Free | Free |
| Sleep/Pause | Auto-sleep after inactivity | Manual pause to stop billing |

### Changes Made

1. **Removed `Dockerfile`** — Regular GPU Spaces provide a good base image with CUDA + PyTorch pre-installed. No custom Dockerfile needed.

2. **`requirements.txt` contains:** `spaces`, `gradio>=6.15.0`, `duckdb==1.5.3`, `huggingface_hub>=0.26.0`, `llama-cpp-python`

3. **Simplified `app.py` CSS** — Switched from manual dark-theme overrides to `gr.themes.Soft` with IBM Plex fonts. Two-column layout (input left, output right).

4. **Improved `model_inference.py`** — Better model cache path resolution: tries cached 14B, then 7B, then downloads from HF Hub.

### Actions Required (User)

1. **Switch hardware** in Space Settings: Zero GPU → Nvidia T4 - small ($0.40/hr)
2. **Add environment variable** in Repository Secrets: `CMAKE_ARGS` = `-DGGML_CUDA=on`
3. **Apply for Community GPU Grant** (button in Settings, bottom left): Free GPU time for non-commercial demos. 1-2 day approval turnaround.

### Expected Outcome

Once switched to T4:
- Docker build will use HF's standard GPU image (CUDA toolkit available)
- `llama-cpp-python` will compile with CUDA support via `CMAKE_ARGS`
- The 14B model (~9GB) fits in T4's 16GB VRAM with room for 4K context
- Space starts and runs normally with GPU-accelerated SQL generation
- Cost: ~$0.40/hr, pause anytime to stop billing

### Fallback Options

| Option | Pros | Cons |
|--------|------|------|
| **L4 ($0.80/hr)** | 24GB VRAM, faster | 2x cost |
| **A10G small ($1.00/hr)** | 24GB, fastest under $2 | 2.5x cost |
| **Community GPU Grant** | Free GPU time | 1-2 day wait for approval |

---

## Final Resolution (IMPLEMENTED): Stay on ZeroGPU with transformers + LoRA

The T4 switch proposed above was **not** needed. The root insight from Issue #3
is architectural: ZeroGPU's CUDA is a PyTorch-only emulation layer, so the fix
was to stop using llama.cpp on the Space and use PyTorch-native inference.

### What shipped (commits `de794a7` → `3cf2ed0`)

1. **Inference backend swap** (`de794a7`): `model_inference.py` rewritten around
   transformers + PEFT. Loads the pre-quantized 4-bit base
   (`unsloth/qwen2.5-coder-14b-instruct-bnb-4bit`, ~10 GB) and applies the LoRA
   adapter (`build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora`, 551 MB) —
   the exact QLoRA training-time configuration. The wrapper (`TransformersLLM`)
   keeps the llama.cpp call/response schema, so `generate_sql`/streaming and
   `app.py` logic were unchanged. `requirements.txt`: `llama-cpp-python` out;
   `torch/transformers/peft/bitsandbytes/accelerate` in.
   *The adapter was recovered from the Modal volume `lfed-training-data`
   (`lora-adapter-v2/`) and published to HF Hub — the merged fp16 model had
   only ever existed in an ephemeral container.*

2. **ZeroGPU adapter-load fix** (`e8c46ef`): PEFT loads adapter safetensors
   straight to `cuda:0` by default, which ZeroGPU forbids at startup
   ("No CUDA GPUs are available"). Fix: `PeftModel.from_pretrained(...,
   torch_device="cpu")` — CPU tensors are then copied into the emulated-CUDA
   LoRA layers via normal torch ops.

3. **Performance** (`2eccdc1`): streaming generator UI (tokens appear in ~2-3 s
   instead of a blank wait), few-shots trimmed 7→4 (prefill cost),
   `spaces.GPU(duration=30)` (shorter durations get queue priority),
   `max_tokens=192`. Measured generation: ~5 s/query; remaining latency is
   ZeroGPU queue + per-call weight restore (the price of free).

4. **Deterministic seed data** (`3cf2ed0`): `.gitignore` was excluding
   `data/*.parquet`, so the Space only had 2 of 5 Parquet files →
   `seed_database()` fell to the Python generator on **every request** with an
   advancing RNG → different data per query (1411 vs 1446 discipline rows).
   Fixed: all 5 Parquet files committed via LFS (byte-deterministic,
   regenerated together), startup check requires all 5, and
   `generate_seed_data()` re-seeds the RNG per call.

### Current state

- **Space (`main`)**: ZeroGPU, transformers + bnb-4bit + LoRA. Free. Working.
- **Local (`local-llamacpp-v1` tag / `product` branch)**: llama.cpp + GGUF —
  the right backend for Mac/Metal and the base for the local-first product.
- **Rule of thumb**: llama.cpp ⇒ real GPU (T4+) or CPU/Metal; ZeroGPU ⇒
  PyTorch-only (transformers, bitsandbytes OK; raw CUDA libs never work).
