---
id: lfed-mod-training
type: module-design
status: draft
title: training — schema-curated pair generation and fine-tuned adapters
parent: lfed-architecture
---

## Responsibility

Produce the weights `nl_query/` loads: natural-language→SQL pairs validated against the real warehouse, and the adapters that come from them. The published output today is the r=64 warehouse LoRA `KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64` on base `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit`, trained from a 25,886-pair synthetic set at `KDDSTLC/lfed-training-data`.

```
training_schema.json  19 curated tables / 492 columns + key_values — the prompt context
generate_pairs.py     local generator: draft pairs, EXECUTE each candidate against the
                      warehouse, discard anything that fails or is non-deterministic
modal_generate.py     Modal A100 + vLLM Qwen2.5-72B-Instruct-AWQ, mass generation
```

## The rule that matters

**A pair exists only if its SQL ran against the real warehouse.** Generation is validated by execution, so the dataset is a set of questions this schema can actually answer. Any new generator mode — governed/Metrics SQL, a different warehouse, a smaller teacher model — has to keep that property, or the adapter starts learning queries that the guard will reject.

`generate_pairs.py` opens `oss_framework/data/analytics.duckdb` read-only and seeds question/SQL style from `nl_query/prompts.py` by path, so this module is coupled to the client's prompt file. That coupling is why the client's schema drift (see `lfed-mod-nl-query` Known drift) propagates into training data.

## Boundary

- Reads the warehouse; writes `training/pairs.jsonl` and HF datasets. Never writes the warehouse, never serves a user.
- Weights stay out of git (`models/` ships only a README; `.gitignore` covers `models/lora-warehouse-r64/`). The documented fetch is `hf download … --local-dir models/lora-warehouse-r64` (~1.1 GB adapter).
- Generation backends are undeclared dependencies: `dspy`, `modal`, `vllm` appear in no `pyproject.toml` extra.

## Known state to fix

- `training/README.md` documents `modal_export_gguf.py` — merge LoRA into fp16 base, convert to GGUF, quantize Q4_K_M, write to the `lfed-gguf-export` Modal volume. **The file does not exist.** This is the on-device export path that `lfed-app-inference` needs for a ≤4B GGUF, so the missing script is now a blocker for the app's small-model budget, not a documentation nit.
- The current adapter is a 14B model on a 4-bit base: roughly 9 GB resident, outside the 16 GB / ~8 GB budget `lfed-app-architecture` is built to. Nothing trained here today satisfies the app's sizing requirement; a small-model run is new work in this module.
- `training_schema.json` covers `main_core` / `main_analytics` / `main_staging` marts only. No metrics views, consistent with `lfed-docs-known-issues`.

## Consumers

`lfed-mod-nl-query` loads the adapters. `lfed-app-architecture` binds to this module's *contract* — "a local model that emits guarded DuckDB SQL for this schema" — not to any checkpoint, so a retrain here is not a frontend dependency.
