# Session Handoff — Kasualdad LFED Build

> **Last updated:** 2026-06-06 (Session 2 — Phases 1-8 complete)
> **Deadline:** 2026-06-15 (HF Build Small Hackathon — "Backyard AI" chapter)
> **Project root:** `/Users/flucido/projects/build-small-hackathon/Kasualdad_LFED`
> **Original reference project:** `/Users/flucido/projects/Kasualdad_LFED` (untouched snapshot)
> **Reference project:** `/Users/flucido/projects/local-data-stack` (education data stack patterns)

---

## TL;DR — How to Resume in 30 Seconds

```bash
cd /Users/flucido/projects/build-small-hackathon/Kasualdad_LFED
source .venv/bin/activate
python -c "import gradio, duckdb, llama_cpp, huggingface_hub; print('env OK')"

# Run the app
python app.py

# Run tests
pytest tests/ -v

# Kick off Modal fine-tuning (after setting HF_TOKEN secret)
modal run modal_train/modal_app.py
```

Full plan is in [`docs/PLAN.md`](./PLAN.md).

---

## Project Summary

**Kasualdad LFED** = a Hugging Face Space that turns natural-language questions from school district admins (principals, superintendents, department heads) into safe DuckDB SQL via a small local LLM (llama.cpp, GGUF format). Targets HF "Build Small" Hackathon badges:

- **Off the Grid** — all inference local, no API calls
- **Well-Tuned** — Modal fine-tune of a small text-to-SQL model pushed to Hub
- **Llama Champion** — llama.cpp as inference backend
- **Off-Brand** — custom CSS targeting cognitive-load reduction (added in second iteration)

User's success criteria: **win the hackathon** + have a **demoable slice for clients/employers**.

---

## Decisions Locked (do not re-litigate)

| Decision | Value | Source |
|---|---|---|
| Project location | `~/projects/build-small-hackathon/Kasualdad_LFED` | User: "this is where the hackathon is happening" |
| Source of truth | Copy of `~/projects/Kasualdad_LFED` | User choice (Recommended) |
| Python version | 3.12 (local + Space) | User: "ok to recreate" |
| Base model | `Qwen2.5-Coder-7B-Instruct` Q4_K_M | Plan, **7/7 sanity check passed** |
| Alt model (fallback) | `Llama-3.1-8B-Instruct` Q4_K_M | Plan (only if Qwen fails sanity) |
| Quantization | Q4_K_M (~4.4 GB) | Plan: speed/accuracy tradeoff for free Space |
| Code layout | Modular: `app.py` / `data_engine.py` / `model_inference.py` / `prompts.py` | User choice (Recommended) |
| Data source | Seed tables only for hackathon | User choice (Recommended) |
| Aesthetic | Linear / Vercel style, minimal monochrome + teal accent | User choice (Recommended) |
| Accent color | `#14b8a6` (teal) | User choice (Recommended) |
| Modal timing | Start fine-tune ASAP, end-to-end | User choice (Recommended) |
| Modal account | `flucido` | User |
| Modal credits | Hackathon-provided, confirmed | User |
| Custom CSS | **Yes** (reinstated after user feedback) | User: "i wnat the design to llook good" |

---

## Current State (as of session 2 — Phases 1-8 complete)

### ✅ Completed
- **Phase 0: Bootstrap** — venv, pinned deps, packages.txt
- **Phase 1: Model sanity check** — Qwen2.5-Coder-7B Q4_K_M: **7/7 prompts passed**, model locked
- **Phase 2: Refactor** — modular codebase (`app.py`, `data_engine.py`, `model_inference.py`, `prompts.py`)
- **Phase 3: Robustness** — JSON envelope parsing, schema-aware column validation (EXPLAIN), threading timeout via `conn.interrupt()`, per-request DB connections, streaming SQL generation
- **Phase 4: Seed data** — `data/generate_seed.py`: 5 schools × 4 years × 13 grades, 2,900 students, 15% chronic rate
- **Phase 5: UI polish** — Off-Brand CSS (Inter + JetBrains Mono, teal accent, WCAG AA, prefers-reduced-motion, focus rings), README design docs
- **Phase 6: Tests** — **81 tests, 0 failures** (execution guard, data engine, model inference with mocked LLM)
- **Phase 7: Modal pipeline** — `modal_train/`: synthetic data generator (1,289 pairs, 32 templates), Unsloth QLoRA train.py, GGUF export, Modal orchestration
- **Phase 8: README** — expanded with badges, Mermaid architecture diagram, schema docs, run guide, project structure

### 🟡 In Progress
- Nothing in progress

### ⏳ Pending
- Phase 7b: Actually run Modal training (user needs to create HF_TOKEN secret and `modal run`)
- Phase 7c: Swap `REPO_ID` in `model_inference.py` after GGUF is pushed
- Phase 9: Deploy to HF Space + smoke test
- Phase 10–11: Buffer + polish + submit

---

## File Tree (Current — post Phase 8)

```
~/projects/build-small-hackathon/Kasualdad_LFED/
├── .venv/                              # Python 3.12.8
├── app.py                              # Gradio UI + Off-Brand CSS (354 lines)
├── data_engine.py                      # DuckDB lifecycle, execution guard, timeout (310 lines)
├── model_inference.py                  # llama.cpp wrapper, streaming (211 lines)
├── prompts.py                          # System prompt, schema docs, few-shot (131 lines)
├── data/
│   └── generate_seed.py                # 5 schools × 4 years seed generator
├── tests/
│   ├── conftest.py                     # Shared fixtures
│   ├── test_execution_guard.py         # 24 tests — SQL injection, validation
│   ├── test_data_engine.py             # 23 tests — schema, isolation, integrity
│   └── test_model_inference.py         # 24 tests — prompt assembly, mock LLM
├── modal_train/
│   ├── generate_synthetic.py           # 1,289 NL→SQL training pairs
│   ├── train.py                        # Unsloth QLoRA recipe
│   ├── export_gguf.py                  # Merge → GGUF → HF Hub
│   ├── modal_app.py                    # Modal orchestration
│   └── train.jsonl                     # Training data (1,289 pairs)
├── docs/
│   ├── HANDOFF.md                      # this file
│   └── PLAN.md                         # full plan
├── requirements.txt                    # PINNED (4 deps)
├── packages.txt                        # System deps for HF Space
└── README.md                           # Expanded (badges, mermaid, schema, run guide)

# External artifacts:
/tmp/lfed-models/qwen/Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf   # 4.4 GB, ready
```

---

## Quick-Reference: Commands to Know

### Activate environment
```bash
cd /Users/flucido/projects/build-small-hackathon/Kasualdad_LFED
source .venv/bin/activate
```

### Test all imports
```bash
python -c "import gradio, duckdb, llama_cpp, huggingface_hub; print('env OK')"
```

### Run the app locally
```bash
python app.py
# → http://localhost:7860
```

### Run pytest (Phase 6+)
```bash
pytest tests/ -v
```

### Modal CLI (Phase 7+)
```bash
modal --version                           # verify install
modal secret list                         # list secrets
modal run modal_train/modal_app.py        # kick off training
```

---

## Outstanding Dependencies

| When | Dependency | Status |
|---|---|---|
| Now | `modal secret create huggingface HF_TOKEN=<token>` | ⏳ User action |
| After training | Swap `REPO_ID` in `model_inference.py` to the fine-tuned GGUF repo | ⏳ After Phase 7c |

---

## 9-Day Schedule (Updated)

| Day | Date | Phases | Status |
|---|---|---|---|
| 1 | Jun 6 | 0 · 1 · 2 · 3 · 4 · 5 · 6 · 7 · 8 | ✅ **Done** (all 8 phases in one session) |
| 3 | Jun 8 | 7b: Modal training (3-6 hrs overnight on A10G) | ⏳ User action needed |
| 4 | Jun 9 | 7c: merge → GGUF → push → swap REPO_ID | ⏳ After training |
| 5–6 | Jun 10–11 | 9: Deploy to HF Space + smoke test | ⏳ |
| 7–8 | Jun 12–13 | Buffer: polish, re-iterate | ⏳ |
| 9 | Jun 14 | Final verify + submit | **Submit** |

**Next action**: User creates Modal HF_TOKEN secret, then `modal run modal_train/modal_app.py`.

---

## Reference

- Full plan: [`docs/PLAN.md`](./PLAN.md)
- HF Build Small Hackathon (track: Backyard AI): submission deadline 2026-06-15
- Modal: https://modal.com/apps/flucido/main (credits: hackathon-provided)
- HF Hub: fine-tuned GGUF repo (TBD — see Modal export script)
