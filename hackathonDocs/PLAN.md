# Full Plan — Kasualdad LFED

> Reference: produced 2026-06-06 in session 1, used to drive [`HANDOFF.md`](./HANDOFF.md)

---

## Why this project

A school-district admin (principal, superintendent, dept. head) types a natural-language question → the app returns the answer as a table + chart, with the SQL shown for transparency. All inference is local (llama.cpp, GGUF). No data leaves the machine. Model is a small open LLM fine-tuned on text-to-SQL via Modal. Runs on a free Hugging Face Space.

**Target**: win the HF "Build Small" Hackathon (Chapter One: Backyard AI) + produce a credible demo slice for clients/employers.

---

## 9-Day Schedule (Locked)

| Day | Date | Phase | Work | Output |
|---|---|---|---|---|
| 1 | Jun 6 | 0 | Bootstrap (3.12 venv, packages.txt, pinned requirements) | Working 3.12 env |
| 1 | Jun 6 | 1 | Model sanity check (Qwen2.5-Coder-7B Q4_K_M) | Locked model name |
| 1 | Jun 6 | 2 | Refactor: `data_engine.py` / `model_inference.py` / `prompts.py` / `app.py` | Modular codebase |
| 2 | Jun 7 | 3 | Robustness: column validation, read-only wrap + LIMIT, timeout, JSON parser, streaming, per-request DuckDB conn | Bulletproof pipeline |
| 2 | Jun 7 | 4 | Data: realistic seed (5 schools × 4 years, populated chronically-absent flag) | Demoable queries |
| 3 | Jun 8 | 5 | UI polish (Linear/Vercel + teal + Off-Brand criteria) | Polished Space |
| 3 | Jun 8 | 6 | Tests (execution_guard, data_engine, model_inference) | Green pytest |
| 3 | Jun 8 | 7a | Synthetic NL→SQL pairs (2–3k) | `train.jsonl` |
| 3→4 | Jun 8–9 | 7b | Modal Unsloth QLoRA (A10G, ~3–6 hrs, **overnight**) | Fine-tuned adapter |
| 4 | Jun 9 | 7c | Merge → GGUF Q4_K_M → push to HF → swap `REPO_ID` | Custom model live |
| 4–5 | Jun 9–10 | 8 | README (frontmatter, mermaid, badges, design doc, demo GIF) | Submission-ready README |
| 5–6 | Jun 10–11 | 9 | Deploy to Space, cold-start verify, end-to-end smoke test | Live demo URL |
| 7–8 | Jun 12–13 | 10 | Buffer: prompt iteration, UX hardening, retrain if needed | Polish |
| 9 | Jun 14 | 11 | Final verification + submit | Submitted |

**Critical path**: Phase 7 (fine-tuning). Starting it on Day 3 gives a full day of compute buffer if a re-train is needed.

---

## Phase Details

### Phase 0 — Bootstrap ✅ DONE
- Project copied to `~/projects/build-small-hackathon/Kasualdad_LFED/`
- venv at Python 3.12.8
- `requirements.txt`: gradio==6.16.0, duckdb==1.5.3, llama-cpp-python==0.3.26, huggingface_hub==1.18.0
- `packages.txt`: cmake, build-essential, libopenblas-dev
- All imports verified

### Phase 1 — Model sanity check 🟡 IN PROGRESS
- ✅ Identified candidate GGUFs (mradermacher quantizer for both)
- ✅ Downloaded Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf to `/tmp/lfed-models/qwen/` (4.4 GB)
- ❌ Run inference on 10 hand-crafted prompts to confirm SQL quality
- ⏸️ Llama-3.1-8B-Instruct Q4_K_M — only download if Qwen fails

**Sanity-check command** is in [`HANDOFF.md`](../docs/HANDOFF.md) under "Phase 1: Sanity-Check Resume".

### Phase 2 — Refactor
- Extract `data_engine.py` (DuckDB, schema introspection, `execute_safe()`)
- Extract `model_inference.py` (Llama lifecycle, `generate_sql()`, streaming)
- Extract `prompts.py` (system prompt + few-shot examples + schema docstring)
- Slim `app.py` to UI + controller

### Phase 3 — Robustness
- Parse the JSON `{sql, explanation}` envelope (fall back to ```sql``` block)
- Validate column names exist in schema (AST parse, not regex)
- Reject any non-SELECT; wrap as `SELECT * FROM (<user_query>) LIMIT 1000`
- Per-query timeout via `duckdb.set_query_timeout`
- Thread safety: per-request DuckDB connection (cheap, in-memory)
- Streaming: yield tokens to Gradio's `stream=True` callback
- Error UX: surface clean messages in UI

### Phase 4 — Data
- 5 schools, 4 school years (`2021-2022` … `2024-2025`), 12 grade levels
- Attendance with `is_chronically_absent` populated ~15% true
- Document schema in README

### Phase 5 — UI polish (Off-Brand badge)
- Custom CSS injected via `gr.Blocks(css=...)` on top of Gradio default
- Inter (UI) + JetBrains Mono (code)
- Single accent color (#14b8a6 teal), neutral grays
- Single column, max-width 960px
- Smooth state changes (120ms ease-out), 200ms result reveal
- Honors `prefers-reduced-motion`
- Example-query chips: 4–6 one-click starters
- Mobile/responsive sanity

### Phase 6 — Tests
- `test_execution_guard.py`: malicious inputs, malformed JSON, missing columns, multi-statement
- `test_data_engine.py`: schema introspection, timeout, empty result
- `test_model_inference.py`: mock the LLM, verify prompt assembly and JSON parsing

### Phase 7 — Modal fine-tuning (Well-Tuned badge)
- `generate_synthetic.py`: 2–3k (NL question, SQL) pairs from seed schema
- `train.py`: Unsloth + QLoRA, ~3 epochs, A10G on Modal (free credits)
- `export_gguf.py`: merge LoRA → GGUF Q4_K_M → push to new HF repo
- `app.py` swaps `REPO_ID` to fine-tuned model
- Verify accuracy improvement on a held-out prompt set

**Modal config**:
```python
import modal
app = modal.App("kasualdad-lfed-train")
# image: unsloth + transformers + trl + bitsandbytes
# volume: /data for training pairs
# secret: HF_TOKEN (for Phase 7c push)
@app.function(gpu="A10G", timeout=4*3600, secrets=[modal.Secret.from_name("huggingface")])
def train(...):
    ...
```

**HF repo name (TBD username)**: `<hf-username>/lfed-qwen2.5-coder-7b-sql-gguf`

### Phase 8 — README
- Frontmatter: `tags: text-to-sql, education, local-first, llama-cpp, duckdb`
- Mermaid architecture diagram
- Badge checklist with links
- 30-second demo GIF
- "How to run locally" section

### Phase 9 — Deploy & verify
- `python app.py` boots, sample queries return correct results
- Push to HF Space, watch cold start (model download, GGUF cache)
- Submit to hackathon with Space URL + HF model repo + brief write-up

---

## Out of Scope (defer or skip)

- ❌ Real Parquet/CSV data lake loader — seed tables only
- ❌ Per-request data file upload — fixed schema
- ❌ User accounts / auth — single-user demo
- ❌ Chart auto-generation — basic dataframe display only
- ❌ Detailed observability/logging beyond stderr

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `gradio==6.16.0` may not exist on Spaces | Verified on PyPI; if Space rejects, downgrade to 5.x |
| Modal cold start eats the A10G budget | Cache image; warm-up job; free credits = no budget pressure |
| Synthetic data quality is too low → bad fine-tune | Hand-validate 50 pairs before training; iterate prompt template if model can't generalize |
| HF Space cold start > 5 min (8B model download) | Q4_K_M (~4.4 GB) fits well; add startup log |
| llama-cpp-python wheel not available for Py 3.12 | `packages.txt` includes build tools; pin a known-good version |
| User provides wrong HF username | Repo name is a one-line swap on Day 4 |

---

## Outstanding Dependencies (chronological)

| When | Need | Status |
|---|---|---|
| Day 1 (now) | — | ✅ Unblocked |
| Day 3 | Modal secret `huggingface` (HF token) | ⏳ Pending |
| Day 4 | HF username (user said `kasualdad` was wrong) | ⏳ Pending |
