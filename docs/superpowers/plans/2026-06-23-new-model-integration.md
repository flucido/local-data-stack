# New Model Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the new r=64 warehouse-trained LoRA adapter into the local-data-stack NL→SQL layer, commit it safely, build an evaluation harness, verify the Gradio app end-to-end, and document the Rill metrics gap.

**Architecture:** The new LoRA adapter (`models/lora-warehouse-r64/`) is uploaded to a new HF repo (`KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`), keeping the old r=32 adapter intact as a rollback. `model_inference.py` defaults to the new repo with local-fallback. A manually-curated eval test set drives an execution-match scorer that compares old vs new. The Gradio app is verified end-to-end locally. The Rill metrics gap is documented as a known issue.

**Tech Stack:** Python 3.12, transformers + PEFT, DuckDB, pytest, Gradio, Hugging Face Hub (`hf` CLI), Modal (for training pipeline reference only)

## Global Constraints

- **Python >= 3.12** (project floor, `pyproject.toml`)
- **DuckDB warehouse** at `oss_framework/data/analytics.duckdb` (878MB, the current dbt output — `data/warehouse.duckdb` is a 12KB stub and `data_engine.py` falls back to the oss_framework path)
- **No 1.1GB safetensors in git** — adapter weights live on HF Hub; `models/` is gitignored
- **Test command:** `cd nl_query && python -m pytest tests/ -v` (tests mock the LLM; no GPU needed)
- **Read-only queries only** — `data_engine.validate_sql()` enforces SELECT-only against exposed schemas
- **HF org:** `KDDSTLC`, logged in as `Kasualdad`
- **Old adapter repo:** `KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora` (r=32, synthetic 5-table schema) — do NOT modify
- **New adapter repo:** `KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64` (r=64, real warehouse schema) — create new
- **Old adapter was previously referenced as `build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora`** — the KDDSTLC mirror is the same model

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `.gitignore` | Modify | Add `models/`, `training/__pycache__/`, `.understand-anything/` |
| `models/README.md` | Create | Document where weights come from, how to fetch, checksum |
| `models/lora-warehouse-r64/` | gitignore | Local adapter weights (1.1GB) — NOT in git |
| `nl_query/model_inference.py` | Modify | Already changed locally — verify, finalize HF repo default |
| `nl_query/test_model.py` | Move to `nl_query/tests/` or delete | Smoke test — fold into eval harness instead |
| `nl_query/tests/test_model_inference.py` | Modify | Update tests for new default adapter path |
| `nl_query/tests/test_eval_harness.py` | Create | Eval harness tests (mocked LLM, test-set loading, scorer) |
| `nl_query/eval.py` | Create | Eval harness: load test set, run model, score execution match |
| `nl_query/eval_test_set.jsonl` | Create | Manually curated held-out test set (questions + gold SQL) |
| `nl_query/tests/test_gradio_e2e.py` | Create | Gradio app integration test (mocked LLM) |
| `docs/known-issues-rill-metrics-gap.md` | Create | Document the Rill metrics layer gap |
| `training/generate_pairs.py` | gitignore `.pyc` only | Keep source — already untracked, commit it |
| `training/modal_generate.py` | Commit | Keep source — already untracked, commit it |
| `training/training_schema.json` | Commit | Keep source — already untracked, commit it |
| `quick.md` | Delete | Scratch file, not part of the project |
| `docs/dbguide*.docx` | Commit | CDE reference docs — commit to docs/ |

---

## Task 1: Gitignore weights, clean up, commit code

**Files:**
- Modify: `.gitignore`
- Create: `models/README.md`
- Delete: `quick.md`
- Move: `nl_query/test_model.py` → delete (replaced by eval harness)

**Interfaces:**
- Produces: A clean working tree where weights are gitignored, code is committed, repo stays small

- [ ] **Step 1: Update `.gitignore`**

Read the current `.gitignore` and append:

```
# Local model weights — fetch from HF Hub, do not commit
models/lora-warehouse-r64/
models/*/adapter_model.safetensors
models/*/adapter_model.bin

# Training artifacts
training/__pycache__/
training/pairs.jsonl
training/pairs_*.jsonl

# Tooling artifacts
.understand-anything/
```

- [ ] **Step 2: Create `models/README.md`**

```markdown
# Local Model Adapters

Adapter weights are NOT committed to git. Fetch them from Hugging Face Hub.

## lora-warehouse-r64

Trained on the real warehouse schema (main_core, main_analytics, main_staging).
Rank 64, alpha 64, all linear layers.

**HF repo:** `KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`
**Base model:** `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit`
**Size:** ~1.1 GB

### Fetch

```bash
# From repo root
hf download KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  --local-dir models/lora-warehouse-r64
```

### Verify (optional)

```bash
sha256sum models/lora-warehouse-r64/adapter_model.safetensors
# Compare against the checksum in the HF repo's model card
```

### Override

`model_inference.py` resolves the adapter in this order:
1. `LFED_ADAPTER_REPO` env var (HF repo id or local path)
2. `models/lora-warehouse-r64/` (local path, this directory)
3. Falls back to the HF repo id if local path is missing
```

- [ ] **Step 3: Delete `quick.md` and `nl_query/test_model.py`**

```bash
rm quick.md
rm nl_query/test_model.py
```

The smoke test is replaced by the eval harness (Task 3) and the E2E test (Task 4).

- [ ] **Step 4: Verify `models/lora-warehouse-r64/` is now ignored**

```bash
git status --short
# models/lora-warehouse-r64/ should NOT appear in untracked files
# training/*.py, training/training_schema.json should still appear
```

- [ ] **Step 5: Stage and commit**

```bash
git add .gitignore models/README.md training/generate_pairs.py \
  training/modal_generate.py training/training_schema.json \
  docs/dbguideacad25.docx docs/dbguidechron25.docx docs/dbguideelp25.docx \
  docs/dbguideintro25.docx nl_query/model_inference.py
git commit -m "feat: wire new r=64 warehouse LoRA adapter; gitignore weights

- model_inference.py defaults to local models/lora-warehouse-r64/
  with LFED_ADAPTER_REPO env override
- .gitignore excludes the 1.1GB safetensors from git
- models/README.md documents how to fetch weights from HF Hub
- training/ pipeline (generate_pairs, modal_generate, schema) committed
- CDE data guide docs committed
- Removes scratch file quick.md and ad-hoc test_model.py"
```

---

## Task 2: Upload new adapter to Hugging Face Hub

**Files:**
- Upload: `models/lora-warehouse-r64/*` → `KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`
- Create: HF model card (README.md on the repo)

**Interfaces:**
- Produces: A downloadable HF repo that `model_inference.py` can fall back to

- [ ] **Step 1: Create the new HF repo**

```bash
hf repo create KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  --type model --yes
```

Expected: repo created successfully.

- [ ] **Step 2: Upload adapter files**

```bash
hf upload KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  models/lora-warehouse-r64 \
  --local-dir models/lora-warehouse-r64
```

Expected: all 5 files uploaded (adapter_config.json, adapter_model.safetensors, chat_template.jinja, tokenizer_config.json, tokenizer.json).

- [ ] **Step 3: Write and upload a model card**

Create a temporary `models/lora-warehouse-r64/README.md` (this one IS uploaded to HF, it's the model card — but it's gitignored locally so it won't bloat git):

```markdown
---
library_name: peft
base_model: unsloth/qwen2.5-coder-14b-instruct-bnb-4bit
tags:
  - lora
  - sft
  - text-to-sql
  - education
  - local-first
  - duckdb
license: apache-2.0
language: en
---

# LFED SQL Assistant v2 — Qwen2.5-Coder-14B-LoRA (Warehouse r=64)

Trained on the **real DuckDB warehouse schema** (main_core, main_analytics,
main_staging — ~30+ tables) for the Local First Education Data Framework.

## Differences from v1

| | v1 (r=32) | v2 (r=64) |
|---|-----------|-----------|
| Training schema | 5 synthetic tables | Real warehouse (~30 tables) |
| LoRA rank | 32 | 64 |
| Adapter size | ~551 MB | ~1.1 GB |
| Target tables | students, enrollment, attendance, discipline, grades | main_core.*, main_analytics.*, main_staging.* |

## Intended use

Converts natural-language questions about K-12 school data into read-only
DuckDB SQL queries. Designed for the LFED Gradio app.

## Training data

Synthetic NL→SQL pairs generated against the real warehouse schema using
Qwen2.5-72B-Instruct-AWQ via vLLM on Modal A100-80GB. Every generated SQL
was validated by executing it against the real DuckDB warehouse.

## How to use

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "unsloth/qwen2.5-coder-14b-instruct-bnb-4bit"
adapter = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64"

model = AutoModelForCausalLM.from_pretrained(base, device_map="auto")
model = PeftModel.from_pretrained(model, adapter, torch_device="cpu")
tokenizer = AutoTokenizer.from_pretrained(adapter)
```

## Known limitations

- Trained on synthetic data against the real schema; may hallucinate columns
- Does not know about Rill metrics views (see project docs for the known gap)
- Requires CUDA for 4-bit inference (bnb); CPU/MPS needs a different base model
```

Upload it:

```bash
hf upload KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  models/lora-warehouse-r64/README.md \
  --path-in-repo README.md
```

- [ ] **Step 4: Verify the repo is accessible**

```bash
hf download KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  --local-dir /tmp/verify-hf-download --include "adapter_config.json"
cat /tmp/verify-hf-download/adapter_config.json | head -5
rm -rf /tmp/verify-hf-download
```

Expected: file downloads and contains `"r": 64`.

- [ ] **Step 5: No git commit needed (weights are on HF, not in git)**

This task produces no git changes. The local `models/lora-warehouse-r64/README.md`
is gitignored. Document the HF repo URL in a commit to `models/README.md` if
Step 1 didn't include it — but Step 1 already does.

---

## Task 3: Update model_inference.py and its tests

**Files:**
- Modify: `nl_query/model_inference.py` (finalize the already-local change)
- Modify: `nl_query/tests/test_model_inference.py`

**Interfaces:**
- Produces: `model_inference.ADAPTER_REPO` resolves to the new HF repo id with local fallback; `LFED_ADAPTER_REPO` env var overrides both

- [ ] **Step 1: Finalize `model_inference.py` adapter resolution**

The current uncommitted change defaults to the local path. Update it to
prefer the HF repo id, with local path as fallback (better for fresh clones):

```python
# ── Model configuration ────────────────────────────────────────────────

BASE_MODEL_4BIT = "unsloth/qwen2.5-coder-14b-instruct-bnb-4bit"

# New r=64 warehouse-trained adapter. Resolution order:
#   1. LFED_ADAPTER_REPO env var (HF repo id or local path)
#   2. Local path models/lora-warehouse-r64/ (if it exists)
#   3. HF Hub repo id (downloaded on first use)
_LOCAL_ADAPTER = str(Path(__file__).resolve().parent.parent / "models" / "lora-warehouse-r64")
_HF_ADAPTER = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64"

def _resolve_adapter() -> str:
    env = os.environ.get("LFED_ADAPTER_REPO")
    if env:
        return env
    if Path(_LOCAL_ADAPTER).exists():
        return _LOCAL_ADAPTER
    return _HF_ADAPTER

ADAPTER_REPO = _resolve_adapter()
BASE_MODEL_4BIT = os.environ.get("LFED_BASE_MODEL", BASE_MODEL_4BIT)
```

- [ ] **Step 2: Update the module docstring**

Change the comment at the top of `model_inference.py` from:

```
Model = pre-quantized 4-bit base (unsloth/qwen2.5-coder-14b-instruct-bnb-4bit)
      + LoRA adapter (build-small-hackathon/lfed-qwen2.5-coder-14b-sql-lora)
```

to:

```
Model = pre-quantized 4-bit base (unsloth/qwen2.5-coder-14b-instruct-bnb-4bit)
      + LoRA adapter (KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64, r=64)
```

- [ ] **Step 3: Write failing test for adapter resolution**

Add to `nl_query/tests/test_model_inference.py`:

```python
class TestAdapterResolution:
    """The adapter repo should resolve from env, local path, or HF."""

    def test_env_override_takes_priority(self, monkeypatch, tmp_path):
        import model_inference
        monkeypatch.setenv("LFED_ADAPTER_REPO", "my-org/my-adapter")
        assert model_inference._resolve_adapter() == "my-org/my-adapter"

    def test_local_path_used_when_present(self, monkeypatch, tmp_path):
        import model_inference
        monkeypatch.delenv("LFED_ADAPTER_REPO", raising=False)
        # Point _LOCAL_ADAPTER at a tmp path that exists
        fake = tmp_path / "fake-adapter"
        fake.mkdir()
        monkeypatch.setattr(model_inference, "_LOCAL_ADAPTER", str(fake))
        assert model_inference._resolve_adapter() == str(fake)

    def test_hf_fallback_when_local_absent(self, monkeypatch, tmp_path):
        import model_inference
        monkeypatch.delenv("LFED_ADAPTER_REPO", raising=False)
        monkeypatch.setattr(model_inference, "_LOCAL_ADAPTER", "/nonexistent/path")
        result = model_inference._resolve_adapter()
        assert result == model_inference._HF_ADAPTER
        assert "KDDSTLC" in result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd nl_query && python -m pytest tests/test_model_inference.py -v
```

Expected: all tests pass including the new `TestAdapterResolution` class.

- [ ] **Step 5: Commit**

```bash
git add nl_query/model_inference.py nl_query/tests/test_model_inference.py
git commit -m "feat: finalize r=64 adapter resolution with HF fallback

- ADAPTER_REPO resolves: env > local path > HF Hub repo
- Updated docstring to reference the new KDDSTLC repo
- Tests cover all three resolution paths"
```

---

## Task 4: Build the held-out eval test set

**Files:**
- Create: `nl_query/eval_test_set.jsonl`

**Interfaces:**
- Produces: A JSONL file with 20 manually curated `{question, sql}` pairs covering all three query paths, held out from training data

This task is manual curation — the user writes the questions. The plan
provides the structure and coverage requirements; the user fills in the
content.

- [ ] **Step 1: Define the test set structure**

Each line is a JSON object:

```json
{"id": "q01", "question": "...", "gold_sql": "...", "path": "core|analytics|staging", "difficulty": "easy|medium|hard"}
```

Coverage requirements (20 questions minimum):

| Path | Count | Tables | Difficulty mix |
|------|-------|--------|----------------|
| core (student-level joins) | 7 | main_core.dim_students, fact_attendance, fact_discipline, fact_academic_records | 3 easy, 3 medium, 1 hard |
| analytics (OBT mart) | 7 | main_analytics.mart_cde_school_accountability | 3 easy, 3 medium, 1 hard |
| staging (direct stg tables) | 6 | main_staging.stg_cde__* | 2 easy, 3 medium, 1 hard |

Rules for curation:
- Questions must NOT appear in `training/generate_pairs.py` SEED_EXAMPLES
- Questions must NOT appear in `nl_query/prompts.py` FEW_SHOT_EXAMPLES
- Gold SQL must execute successfully against `oss_framework/data/analytics.duckdb`
- Mix aggregation types: COUNT, AVG, SUM, comparisons, rankings, filtering
- Include at least 3 questions with reporting_category filters (TA, RH, RB, SE, EL, SWD)
- Include at least 2 questions with year filters in BOTH formats (2023-2024 for Aeries, 2023-24 for CDE)

- [ ] **Step 2: Write the 20 questions**

Create `nl_query/eval_test_set.jsonl`. Example entries (user fills in the rest):

```jsonl
{"id":"q01","question":"How many students were enrolled in 2023-2024?","gold_sql":"SELECT COUNT(DISTINCT student_id_hash) AS student_count FROM main_core.dim_students WHERE academic_year = '2023-2024';","path":"core","difficulty":"easy"}
{"id":"q02","question":"What is the chronic absenteeism rate for Hispanic students across all schools in 2023-24?","gold_sql":"SELECT cds_code, school_name, ca_chronic_absent_rate_pct FROM main_analytics.mart_cde_school_accountability WHERE academic_year = '2023-24' AND reporting_category = 'RH' AND ca_chronic_absent_rate_pct IS NOT NULL ORDER BY ca_chronic_absent_rate_pct DESC;","path":"analytics","difficulty":"easy"}
```

IMPORTANT: Do NOT reuse these exact questions — they are already in the seed
examples. Write NEW questions that test the same paths but with different
specificity, schools, years, and subgroups.

- [ ] **Step 3: Validate every gold SQL executes against the warehouse**

```bash
cd nl_query && python -c "
import json, duckdb
conn = duckdb.connect('../oss_framework/data/analytics.duckdb', read_only=True)
with open('eval_test_set.jsonl') as f:
    for line in f:
        item = json.loads(line)
        try:
            conn.execute(item['gold_sql'])
            print(f\"  {item['id']}: OK\")
        except Exception as e:
            print(f\"  {item['id']}: FAIL - {e}\")
conn.close()
"
```

Expected: all 20 print `OK`. Fix any that fail before proceeding.

- [ ] **Step 4: Commit**

```bash
git add nl_query/eval_test_set.jsonl
git commit -m "test: add 20-question held-out eval test set

Manually curated NL→SQL pairs covering all three query paths
(core student-level, analytics OBT mart, staging tables). Gold SQL
validated against the live warehouse. Held out from training data."
```

---

## Task 5: Build the eval harness

**Files:**
- Create: `nl_query/eval.py`
- Create: `nl_query/tests/test_eval_harness.py`

**Interfaces:**
- Consumes: `nl_query/eval_test_set.jsonl` (Task 4), `nl_query/model_inference.generate_sql` (Task 3), `nl_query/data_engine.extract_sql` + `create_session`
- Produces: `nl_query.eval.run_eval(adapter_repo, test_set_path) -> EvalResult` with execution-match and exact-match scores

- [ ] **Step 1: Write failing tests for the eval harness**

Create `nl_query/tests/test_eval_harness.py`:

```python
"""test_eval_harness.py — Eval harness tests (mocked LLM, no GPU needed)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestLoadTestSet:
    def test_loads_jsonl(self, tmp_path):
        from eval import load_test_set
        p = tmp_path / "test.jsonl"
        p.write_text(json.dumps({"id": "q01", "question": "Q", "gold_sql": "SELECT 1", "path": "core", "difficulty": "easy"}) + "\n")
        items = load_test_set(str(p))
        assert len(items) == 1
        assert items[0]["id"] == "q01"

    def test_skips_malformed_lines(self, tmp_path):
        from eval import load_test_set
        p = tmp_path / "test.jsonl"
        p.write_text('{"id": "q01", "question": "Q", "gold_sql": "SELECT 1"}\nnot json\n')
        items = load_test_set(str(p))
        assert len(items) == 1


class TestExecutionMatch:
    def test_matching_results_score_hit(self):
        from eval import execution_match
        gold_rows = [(1,), (2,)]
        pred_rows = [(1,), (2,)]
        assert execution_match(gold_rows, pred_rows) is True

    def test_different_order_still_matches(self):
        from eval import execution_match
        gold_rows = [(1,), (2,)]
        pred_rows = [(2,), (1,)]
        assert execution_match(gold_rows, pred_rows) is True

    def test_different_results_score_miss(self):
        from eval import execution_match
        gold_rows = [(1,), (2,)]
        pred_rows = [(1,), (3,)]
        assert execution_match(gold_rows, pred_rows) is False

    def test_empty_vs_nonempty(self):
        from eval import execution_match
        assert execution_match([], [(1,)]) is False
        assert execution_match([], []) is True


class TestRunEvalMocked:
    def test_full_flow_with_mock_llm(self, tmp_path):
        """Mock LLM returns gold SQL → should score 100% execution match."""
        from eval import run_eval, load_test_set

        test_set = tmp_path / "test.jsonl"
        test_set.write_text(json.dumps({
            "id": "q01",
            "question": "How many students?",
            "gold_sql": "SELECT COUNT(*) AS c FROM main_core.dim_students WHERE academic_year = '2023-2024'",
            "path": "core",
            "difficulty": "easy",
        }) + "\n")

        mock_llm = MagicMock()
        mock_llm.return_value = {"choices": [{"text": "```sql\nSELECT COUNT(*) AS c FROM main_core.dim_students WHERE academic_year = '2023-2024'\n```"}]}

        with patch("eval.load_model", return_value=mock_llm):
            result = run_eval(
                adapter_repo="mock",
                test_set_path=str(test_set),
                warehouse_path="../oss_framework/data/analytics.duckdb",
            )

        assert result.total == 1
        assert result.execution_hits == 1
        assert result.execution_accuracy == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd nl_query && python -m pytest tests/test_eval_harness.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'eval'`

- [ ] **Step 3: Implement the eval harness**

Create `nl_query/eval.py`:

```python
"""
eval.py — Evaluation harness for NL→SQL models.

Runs a held-out test set through the model, extracts SQL, executes it
against the real warehouse, and compares results to gold SQL.

Usage:
    python eval.py --test-set eval_test_set.jsonl
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora  # old model
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional

import duckdb

from data_engine import extract_sql, validate_sql
from model_inference import generate_sql, load_model


@dataclasses.dataclass
class EvalResult:
    total: int = 0
    execution_hits: int = 0
    exact_hits: int = 0
    errors: int = 0
    timeouts: int = 0
    per_question: list[dict] = dataclasses.field(default_factory=list)

    @property
    def execution_accuracy(self) -> float:
        return self.execution_hits / self.total if self.total > 0 else 0.0

    @property
    def exact_accuracy(self) -> float:
        return self.exact_hits / self.total if self.total > 0 else 0.0


def load_test_set(path: str) -> list[dict]:
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return items


def execution_match(gold_rows: list, pred_rows: list) -> bool:
    gold_set = {tuple(r) for r in gold_rows}
    pred_set = {tuple(r) for r in pred_rows}
    return gold_set == pred_set


def exact_match(gold_sql: str, pred_sql: str) -> bool:
    import re
    def normalize(s: str) -> str:
        s = s.strip().rstrip(";").lower()
        s = re.sub(r"\s+", " ", s)
        return s
    return normalize(gold_sql) == normalize(pred_sql)


def run_eval(
    adapter_repo: str,
    test_set_path: str,
    warehouse_path: str = "../oss_framework/data/analytics.duckdb",
    max_tokens: int = 256,
    timeout_sec: int = 30,
) -> EvalResult:
    items = load_test_set(test_set_path)
    result = EvalResult(total=len(items))

    import os
    os.environ["LFED_ADAPTER_REPO"] = adapter_repo

    # Force model reload with the specified adapter
    import model_inference
    model_inference._llm = None

    conn = duckdb.connect(warehouse_path, read_only=True)

    for item in items:
        qid = item["id"]
        question = item["question"]
        gold_sql = item["gold_sql"]

        entry = {"id": qid, "question": question, "path": item.get("path", ""), "difficulty": item.get("difficulty", "")}

        t0 = time.time()
        try:
            raw_output, _ = generate_sql(question, max_tokens=max_tokens)
            pred_sql = extract_sql(raw_output)
            entry["pred_sql"] = pred_sql
            entry["raw_output"] = raw_output[:200]

            # Execute gold
            gold_rows = conn.execute(gold_sql).fetchall()

            # Validate and execute pred
            validate_sql(pred_sql, conn=conn)
            pred_rows = conn.execute(pred_sql).fetchall()

            if execution_match(gold_rows, pred_rows):
                result.execution_hits += 1
                entry["execution_match"] = True
            else:
                entry["execution_match"] = False
                entry["gold_rows_sample"] = str(gold_rows[:3])
                entry["pred_rows_sample"] = str(pred_rows[:3])

            if exact_match(gold_sql, pred_sql):
                result.exact_hits += 1
                entry["exact_match"] = True
            else:
                entry["exact_match"] = False

        except Exception as e:
            result.errors += 1
            entry["error"] = str(e)[:200]
            entry["execution_match"] = False
            entry["exact_match"] = False

        entry["latency_sec"] = round(time.time() - t0, 2)
        result.per_question.append(entry)

        status = "HIT" if entry.get("execution_match") else "MISS"
        print(f"  {qid}: {status} ({entry['latency_sec']}s) [{item.get('path','')}]")

    conn.close()

    print(f"\n{'='*60}")
    print(f"Results: {result.execution_hits}/{result.total} execution match ({result.execution_accuracy:.1%})")
    print(f"         {result.exact_hits}/{result.total} exact match ({result.exact_accuracy:.1%})")
    print(f"         {result.errors} errors")
    print(f"{'='*60}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Run NL→SQL eval")
    parser.add_argument("--test-set", default="eval_test_set.jsonl")
    parser.add_argument("--adapter", default=None, help="HF repo id or local path (default: current model_inference config)")
    parser.add_argument("--warehouse", default="../oss_framework/data/analytics.duckdb")
    parser.add_argument("--output", default=None, help="Save detailed results as JSON")
    args = parser.parse_args()

    adapter = args.adapter or str(Path(__file__).resolve().parent.parent / "models" / "lora-warehouse-r64")
    if not Path(adapter).exists():
        adapter = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64"

    result = run_eval(adapter, args.test_set, args.warehouse)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(dataclasses.asdict(result), f, indent=2)
        print(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd nl_query && python -m pytest tests/test_eval_harness.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add nl_query/eval.py nl_query/tests/test_eval_harness.py
git commit -m "feat: add eval harness with execution-match scoring

- load_test_set, execution_match, exact_match utilities
- run_eval() runs the full test set through the model and scores
  execution match (result set equality) + exact SQL match
- CLI: python eval.py --test-set eval_test_set.jsonl --adapter <repo>
- Tests mock the LLM so no GPU is needed for the test suite"
```

---

## Task 6: Run the eval (old vs new) and record results

**Files:**
- Create: `nl_query/eval_results_2026-06-23.json` (generated, gitignored or committed as reference)

**Interfaces:**
- Consumes: `nl_query/eval.py` (Task 5), `nl_query/eval_test_set.jsonl` (Task 4)
- Produces: A baseline comparison between old r=32 and new r=64 adapters

This task requires a CUDA GPU (the 14B bnb-4bit model needs CUDA). If running
locally on macOS, skip this task and run on Modal or a GPU machine.

- [ ] **Step 1: Run eval against the NEW adapter (r=64)**

```bash
cd nl_query
python eval.py \
  --test-set eval_test_set.jsonl \
  --adapter "../models/lora-warehouse-r64" \
  --output eval_results_r64.json
```

Record the execution match % and exact match %.

- [ ] **Step 2: Run eval against the OLD adapter (r=32)**

```bash
cd nl_query
python eval.py \
  --test-set eval_test_set.jsonl \
  --adapter "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora" \
  --output eval_results_r32.json
```

Record the execution match % and exact match %.

- [ ] **Step 3: Compare and document**

Create `docs/eval-baseline-2026-06-23.md`:

```markdown
# Eval Baseline — 2026-06-23

## Results

| Metric | Old (r=32, synthetic) | New (r=64, warehouse) | Delta |
|--------|----------------------|----------------------|-------|
| Execution match | XX% | XX% | +XX |
| Exact match | XX% | XX% | +XX |
| Errors | X | X | -X |
| Avg latency | X.Xs | X.Xs | +/-X.Xs |

## Test set

- 20 manually curated questions
- Coverage: core (7), analytics (7), staging (6)
- Difficulty: easy (8), medium (6), hard (6)

## Environment

- Base model: unsloth/qwen2.5-coder-14b-instruct-bnb-4bit
- Warehouse: oss_framework/data/analytics.duckdb
- Run on: [GPU type / Modal / local]

## Conclusion

[Fill in: did the new model improve? By how much? Is it shippable?]
```

- [ ] **Step 4: Commit results**

```bash
git add docs/eval-baseline-2026-06-23.md nl_query/eval_results_r64.json nl_query/eval_results_r32.json
git commit -m "docs: eval baseline comparison — old r=32 vs new r=64 adapter"
```

---

## Task 7: Verify Gradio app end-to-end

**Files:**
- Create: `nl_query/tests/test_gradio_e2e.py`

**Interfaces:**
- Consumes: `nl_query/app.py`, `nl_query/model_inference.py`, `nl_query/data_engine.py`
- Produces: Tests that verify the full question→SQL→result flow with a mocked LLM

- [ ] **Step 1: Write the E2E test**

Create `nl_query/tests/test_gradio_e2e.py`:

```python
"""test_gradio_e2e.py — Gradio app end-to-end tests (mocked LLM).

Tests the full handle_query flow: question → SQL generation → extraction →
validation → execution → result formatting. The LLM is mocked so no GPU
is needed. Requires the warehouse at oss_framework/data/analytics.duckdb.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# conftest.py adds the package root to sys.path
from conftest import warehouse_available


@pytest.fixture
def mock_llm():
    """Mock LLM that returns a valid SQL query."""
    llm = MagicMock()
    llm.return_value = {"choices": [{"text": "```sql\nSELECT COUNT(DISTINCT student_id_hash) AS student_count FROM main_core.dim_students WHERE academic_year = '2023-2024'\n```"}]}
    return llm


@pytest.fixture
def mock_streaming_llm():
    """Mock LLM that yields SQL in chunks (simulates streaming)."""
    sql = "```sql\nSELECT COUNT(DISTINCT student_id_hash) AS student_count FROM main_core.dim_students WHERE academic_year = '2023-2024'\n```"
    chunks = [sql[i:i+10] for i in range(0, len(sql), 10)]
    llm = MagicMock()
    llm.return_value = iter([{"choices": [{"text": c}]} for c in chunks])
    return llm


@pytest.mark.skipif(not warehouse_available(), reason="No warehouse available")
class TestHandleQueryE2E:
    """Full end-to-end query flow with mocked LLM."""

    def test_question_to_result(self, mock_streaming_llm):
        import app

        with patch("app.llm", mock_streaming_llm):
            with patch("model_inference.get_model", return_value=mock_streaming_llm):
                results = list(app.handle_query(
                    "How many students were enrolled in 2023-2024?",
                    prior_state=None,
                ))

        # handle_query yields tuples of (prior, sql, df, emoji, status, state)
        # The last yield should be the successful result
        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji == "✅"
        assert sql is not None
        assert "SELECT" in sql.upper()
        assert df is not None
        assert len(df) > 0

    def test_empty_question_returns_error(self):
        import app

        results = list(app.handle_query("", prior_state=None))
        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji == "🤖"
        assert "ask a question" in status.lower() or "empty" in status.lower()

    def test_invalid_sql_returns_error(self):
        import app

        bad_llm = MagicMock()
        bad_llm.return_value = iter([{"choices": [{"text": "```sql\nDROP TABLE students\n```"}]}])

        with patch("app.llm", bad_llm):
            with patch("model_inference.get_model", return_value=bad_llm):
                results = list(app.handle_query(
                    "Delete all students",
                    prior_state=None,
                ))

        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji in ("⚠️", "❌")
        assert sql is not None  # SQL was generated (even if invalid)


class TestSchemaIntrospection:
    """Verify the warehouse schema is introspected correctly for prompts."""

    @pytest.mark.skipif(not warehouse_available(), reason="No warehouse available")
    def test_get_warehouse_schema_returns_dict(self):
        import app

        # Clear cache to force fresh introspection
        app._schema_cache = None
        schema = app.get_warehouse_schema()
        assert isinstance(schema, dict)
        assert len(schema) > 0
        # Should include core tables
        assert any("dim_students" in k for k in schema.keys())
        # Should NOT include PII tables
        assert not any("pii" in k.lower() for k in schema.keys())
        # Should NOT include dlt bookkeeping
        assert not any("_dlt" in k for k in schema.keys())
```

- [ ] **Step 2: Run tests**

```bash
cd nl_query && python -m pytest tests/test_gradio_e2e.py -v
```

Expected: tests pass (some may skip if warehouse is absent on a fresh clone).

- [ ] **Step 3: Manually verify the app launches with the new adapter**

```bash
cd nl_query
# Verify model_inference resolves to the new adapter
python -c "
import model_inference
print(f'Adapter: {model_inference.ADAPTER_REPO}')
print(f'Base: {model_inference.BASE_MODEL_4BIT}')
"

# If on a GPU machine, launch the app:
# python app.py
# Then ask: "How many students were enrolled in 2023-2024?"
# Verify SQL generates, executes, and returns a result table.
```

Expected: adapter path prints the local path or HF repo id; no import errors.

- [ ] **Step 4: Commit**

```bash
git add nl_query/tests/test_gradio_e2e.py
git commit -m "test: Gradio app end-to-end tests with mocked LLM

- Full question→SQL→execution→result flow test
- Empty question error handling
- Invalid SQL (DROP) rejection test
- Schema introspection verifies PII/dlt tables are excluded"
```

---

## Task 8: Document the Rill metrics gap

**Files:**
- Create: `docs/known-issues-rill-metrics-gap.md`

This is documentation only — no code changes. It records the gap between
the NL→SQL model (trained on raw DuckDB tables) and the project's stated
goal that agents should use Metrics SQL against Rill metrics views (Gate 4
in `.opencode/instructions.md`).

- [ ] **Step 1: Write the known-issues doc**

Create `docs/known-issues-rill-metrics-gap.md`:

```markdown
# Known Issue: NL→SQL Model Does Not Know About Rill Metrics Views

## Status

**Open** — documented 2026-06-23. Not blocking the current integration
but must be addressed before the NL→SQL layer is considered fully
integrated with the Rill dashboards.

## Background

The project instructions (`.opencode/instructions.md`, Gate 4) state:

> AI agents querying data must use Metrics SQL against metrics views,
> not raw SQL against underlying tables.

The current NL→SQL model was trained on raw DuckDB tables:
- `main_core.dim_students`, `main_core.fact_attendance`, etc.
- `main_analytics.mart_cde_school_accountability`
- `main_staging.stg_cde__*`

It does NOT know about Rill metrics views:
- `rill_project/metrics/cde_chronic_absenteeism.yaml`
- `rill_project/metrics/cde_suspension.yaml`
- `rill_project/metrics/cde_ela.yaml`
- `rill_project/metrics/cde_elpac.yaml`

## Impact

The model generates raw DuckDB SQL that bypasses the governed metrics
layer. This means:
1. Metric definitions could diverge between the model's SQL and the
   Rill metrics view definitions.
2. No row-level security or access control from the metrics layer.
3. Dashboard and NL→SQL results may disagree for the same question.

## Options to Resolve

1. **Prompt engineering only** — Add Rill metrics view schemas to the
   prompt and instruct the model to use Metrics SQL. Low effort, but
   the model was not trained on Metrics SQL syntax.

2. **Retrain with Metrics SQL pairs** — Generate new training pairs that
   use Metrics SQL against the Rill metrics views. Higher effort, but
   produces a model that natively speaks the governed layer.

3. **Translation layer** — Keep the model generating raw SQL, but add a
   post-processing step that maps raw SQL to equivalent Metrics SQL.
   Complex and brittle.

## Recommendation

Option 2 (retrain) is the right long-term path, but only after the eval
harness (Task 5) is in place so we can measure the improvement. This
should be a follow-up plan after the current integration is complete.

## References

- `.opencode/instructions.md` — Gate 4
- `rill_project/metrics/` — the four metrics views the model should learn
- `training/generate_pairs.py` — the training data generator (would need
  a Metrics SQL mode)
```

- [ ] **Step 2: Commit**

```bash
git add docs/known-issues-rill-metrics-gap.md
git commit -m "docs: document Rill metrics layer gap in NL→SQL model

The model is trained on raw DuckDB tables, not Rill metrics views.
Gate 4 requires agents to use Metrics SQL. This is a known gap to
be addressed in a follow-up plan after the eval harness is in place."
```

---

## Self-Review

**1. Spec coverage:**
- Commit everything so it's safe → Task 1 (gitignore + commit code)
- Build the evaluation harness → Task 5 (eval.py + tests)
- Wire in the Gradio app → Task 7 (E2E tests + manual verification)
- Connect metrics later → Task 8 (document the gap, don't solve it)
- Retraining pipeline loop → explicitly deferred (mentioned in Task 8)

**2. Placeholder scan:** The only "fill in" is in Task 4 (user writes 20
questions) — this is intentional manual curation, not a placeholder. Task 6
results are filled in after running the eval, which requires a GPU.

**3. Type consistency:** `run_eval` returns `EvalResult` with
`execution_accuracy` and `exact_accuracy` properties — used consistently
in Task 5 tests and Task 6 CLI. `load_test_set` is used in both the test
and the implementation.

**4. Dependency order:** Tasks 1-3 can run in sequence. Task 4 (test set) is
independent of Task 5 (harness) but Task 6 (run eval) needs both. Task 7
needs Task 3. Task 8 is independent.
