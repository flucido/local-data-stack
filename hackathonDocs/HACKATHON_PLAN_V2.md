# LFED Hackathon Plan v2 — Concrete 7-Day Plan

> **Scope:** Single domain (attendance), local-first, M2 Mac 16GB
> **Credits:** $250 Modal
> **Deadline:** June 15, 2026
> **Philosophy:** Hackathon = skill-honing, not production launch

---

## Decision: Model Selection

### Your Constraints
- M2 Mac, 16GB unified memory
- Local-first, no API calls at inference
- llama.cpp + GGUF format
- ~10-11GB usable for model (5GB reserved for OS + Gradio + DuckDB)

### Current Model: Qwen2.5-Coder-7B Q4_K_M (~4.4GB)
Good. Works. Leaves plenty of headroom. But 7B is the floor for complex SQL.

### Upgrade Options That Fit in 16GB

| Model | Params | Q4_K_M Size | SQL Skill | Coding | Notes |
|---|---|---|---|---|---|
| **Qwen2.5-Coder-7B** (current) | 7B | ~4.4 GB | Good | Great | Safe choice, proven |
| **Gemma 4 12B** | 12B | ~7.4 GB | Very good | Great | Brand new, Apache 2.0, multimodal, 256K ctx |
| **Qwen2.5-14B** | 14B | ~8.5 GB | Great | Great | Best in 16GB bracket per apxml.com |
| **Qwen2.5-Coder-14B** | 14B | ~8.5 GB | Great | Best | Coder variant, optimized for code/SQL |
| Gemma 4 E4B | 4.5B | ~3 GB | OK | Good | Too small for reliable SQL |

### Recommendation: Two-Model Strategy

**Inference model (runs on your Mac):** Qwen2.5-Coder-14B Q4_K_M
- 14B is the sweet spot for 16GB Mac — proven by multiple benchmarks
- Coder variant specifically trained on code/SQL tasks
- ~8.5GB leaves ~7.5GB for OS + app overhead
- Unsloth has GGUF versions ready to download
- Fine-tunable on Modal A10G (24GB fits 14B QLoRA)

**Data generation model (runs on Modal):** Qwen2.5-72B-Instruct on A100 80GB
- Much smarter — generates higher quality NL→SQL pairs
- Runs on Modal, not your Mac
- ~$2.50/hr, 3-4 hours = ~$8-10 to generate 10K+ pairs

**Why not Gemma 4 12B?**
- Excellent model, but Qwen2.5-Coder-14B is specifically trained for code/SQL
- Gemma 4 is newer (fewer fine-tuned GGUFs, less community testing for SQL)
- For a SQL-focused hackathon, the Coder variant wins
- Gemma 4 would be a great choice for a general-purpose app

**Why not stay with 7B?**
- You can — it works. But 14B at Q4_K_M fits your Mac with room to spare
- 14B handles complex queries (joins, subqueries, CASE WHEN) noticeably better
- The jump from 7B → 14B is the biggest quality gain per parameter in this range

---

## The Plan: 7 Days to Submission

### Day 1 (Today — June 8): Foundation

**Goal:** Expanded schema + seed data for attendance domain

1. Expand `data_engine.py` schema to include richer attendance tables:
   - Keep existing: `enrollment`, `attendance`
   - Add: `students` (demographics), `discipline` (incidents), `grades` (GPA)
   - This gives the model more to work with while keeping scope tight

2. Generate expanded seed data (10K students, 8 schools, 6 years)
   - Realistic distributions: 15% chronic absenteeism, demographic mix
   - Use CA Department of Education patterns as reference

3. Update `prompts.py` with expanded schema docs

**Time:** ~3 hours
**Modal cost:** $0 (all local)

### Day 2 (June 9): Training Data Generation (Big Model)

**Goal:** 10,000+ NL→SQL pairs using Modal + 72B model

1. Write `generate_synthetic_v2.py` that:
   - Takes your expanded schema as input
   - Calls Qwen2.5-72B on Modal to generate NL→SQL pairs
   - Covers: basic counts, aggregations, GROUP BY, HAVING, CASE WHEN,
     window functions, subqueries, multi-table joins
   - Each pair includes: question, SQL, complexity level

2. Run on Modal A100 80GB (~3-4 hours)
   - Generate 10,000 pairs
   - Validate each SQL against seed data (must execute + return results)
   - Discard failures

3. Combine with your existing 1,289 template pairs

**Time:** ~4 hours (mostly waiting for Modal)
**Modal cost:** ~$10

### Day 3 (June 10): Data Augmentation + Quality

**Goal:** 25,000+ validated pairs with diversity

1. Rephrasing pass: For each validated pair, generate 3 NL variations
   - Formal: "What is the average number of absences per school?"
   - Casual: "What's the avg absences by school?"
   - Abbreviated: "avg absences per school?"
   - Typo-prone: "Whats the avg abscences per scool?"

2. Pull 2,000 relevant pairs from Gretel dataset (free, already validated)
   - Filter for: aggregation, GROUP BY, CASE WHEN, window functions
   - These add general SQL knowledge to complement your domain-specific pairs

3. Final validation: run all SQL against seed data
4. Quality check: sample 100 pairs for manual review

**Target:** 25,000-30,000 validated pairs
**Time:** ~3 hours
**Modal cost:** ~$2-3 (rephrasing on T4)

### Day 4 (June 11): Model Training v2

**Goal:** Fine-tune Qwen2.5-Coder-14B with expanded data

1. Update `train.py`:
   - Base model: `unsloth/Qwen2.5-Coder-14B-Instruct`
   - LoRA rank: 32 (up from 16 — more data supports this)
   - Learning rate: 1e-4 (down from 2e-4 — more data)
   - Epochs: 2 (down from 3 — more data, avoid overfitting)
   - Max seq length: 4096 (up from 2048 — for longer queries)
   - Batch: 4 × 8 = 32 effective

2. Run training on Modal A10G (~2-3 hours for 25K pairs)
   - Monitor loss curve
   - Save checkpoints

3. Export GGUF Q4_K_M

**Time:** ~3-4 hours
**Modal cost:** ~$4-5

### Day 5 (June 12): Evaluation + Model Selection

**Goal:** Pick the best model, verify quality

1. Create eval set: 50 attendance questions with expected SQL
   - Mix of simple, medium, complex
   - Include edge cases (empty results, ambiguous questions)

2. Compare:
   - v1 (Qwen2.5-Coder-7B, 1,289 pairs)
   - v2 (Qwen2.5-Coder-14B, 25K pairs)
   - Unfine-tuned Qwen2.5-Coder-14B (baseline)

3. Metrics:
   - Exact SQL match
   - Execution match (same results)
   - Schema validity (no hallucinated columns)
   - Safety (no DDL/DML)

4. Pick winner, download GGUF to local Mac

**Time:** ~3 hours
**Modal cost:** ~$2

### Day 6 (June 13): Integration + Polish

**Goal:** Working end-to-end demo

1. Update `model_inference.py` to use new model
2. Update `prompts.py` with expanded schema
3. Test end-to-end on Mac M2
4. Polish Gradio UI
5. Update README with v2 results

**Time:** ~4 hours
**Modal cost:** $0 (all local)

### Day 7 (June 14): Deploy + Submit

**Goal:** Live on HuggingFace Spaces

1. Push to HF Space
2. Smoke test on Space (Zero GPU)
3. Record demo if needed
4. Submit to hackathon

**Time:** ~2 hours
**Modal cost:** $0

---

## Budget Summary

| Item | Hours | Modal Cost |
|---|---|---|
| Day 1: Schema + seed data | 3 | $0 |
| Day 2: 72B data generation | 4 | $10 |
| Day 3: Augmentation + Gretel | 3 | $3 |
| Day 4: 14B training | 4 | $5 |
| Day 5: Evaluation | 3 | $2 |
| Day 6: Integration | 4 | $0 |
| Day 7: Deploy | 2 | $0 |
| **Total** | **23** | **~$20** |
| **Remaining credits** | | **~$230** |

You'll use less than 10% of your credits. The rest is bank for future iterations or the expanded multi-domain project post-hackathon.

---

## What This Gets You

**Hackathon submission:**
- Gradio app on HF Spaces
- Fine-tuned 14B model for attendance SQL
- 25K+ training pairs (could open-source this)
- Local-first: runs on M2 Mac with no API calls
- Targets: Off the Grid, Well-Tuned, Llama Champion, Off-Brand badges

**Skills honed:**
- Synthetic data generation with large models
- QLoRA fine-tuning pipeline on Modal
- GGUF export + quantization
- Schema-aware NL→SQL evaluation
- End-to-end ML product deployment

**Post-hackathon assets:**
- Reusable training pipeline (swap schema → new domain)
- $230 Modal credits for expanded project
- Training data generation methodology
- Foundation for LTC school district analytics product

---

## Key Risk: 14B on A10G

Qwen2.5-Coder-14B in 4-bit QLoRA needs ~18-20GB VRAM. A10G has 24GB. This fits, but tighter than 7B. If it OOMs:

**Fallback:** Use Qwen2.5-Coder-7B for training (proven), but evaluate 14B unfine-tuned as inference model. The 14B base model might be good enough without fine-tuning for a single-domain attendance task — test this on Day 5.

---

## Appendix: Where to Get the Models

```bash
# Qwen2.5-Coder-14B GGUF (for local inference)
# Check: huggingface.co/unsloth/Qwen2.5-Coder-14B-Instruct-GGUF
# Or: mradermacher/Qwen2.5-Coder-14B-Instruct-GGUF

# Qwen2.5-Coder-14B (for Modal fine-tuning)
# Unsloth: unsloth/Qwen2.5-Coder-14B-Instruct

# Qwen2.5-72B (for data generation on Modal)
# Qwen/Qwen2.5-72B-Instruct

# Gretel dataset (for augmentation)
# huggingface.co/datasets/gretelai/synthetic_text_to_sql
```
