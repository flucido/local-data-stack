# LFED Training Playbook

> **Last updated:** 2026-06-08
> **Status:** Training actively running on Modal A10G

---

## 1. How the Training Pipeline Works

### Architecture Overview

```
generate_synthetic.py  →  train.jsonl (1,289 pairs)
         ↓
     train.py           →  lora-adapter/ (QLoRA weights)
         ↓
   export_gguf.py       →  GGUF Q4_K_M → HF Hub
```

All three steps run on **Modal** (cloud GPU platform) orchestrated by `modal_app.py`.

### Step-by-Step Commands

```bash
cd /Users/flucido/projects/build-small-hackathon/Kasualdad_LFED
source .venv/bin/activate

# Full pipeline (all 3 steps sequentially)
modal run modal_train/modal_app.py

# Or deploy as persistent app (survives client disconnect)
modal deploy modal_train/modal_app.py

# Monitor progress
modal app logs <app-id>

# Check running apps
modal app list
```

### Prerequisites

| Requirement | How | Status |
|---|---|---|
| Modal account | Sign up at modal.com | ✅ `flucido` |
| Modal credits | Hackathon-provided | ✅ |
| HF_TOKEN secret | `modal secret create huggingface HF_TOKEN=<token>` | ✅ Created |
| HF Hub repo | Auto-created by export_gguf.py | ⏳ After training |

### Training Hyperparameters (Current)

| Param | Value | Notes |
|---|---|---|
| Base model | `unsloth/Qwen2.5-Coder-7B-Instruct` | 7B params, passed 7/7 sanity |
| Quantization | 4-bit QLoRA (bitsandbytes) | Fits A10G 24GB |
| LoRA rank (r) | 16 | |
| LoRA alpha | 16 | Equal to r = stable |
| Target modules | q, k, v, o, gate, up, down proj | All attention + MLP |
| Max seq length | 2048 | |
| Batch size | 4 | |
| Grad accumulation | 4 | Effective batch = 16 |
| Learning rate | 2e-4 | Standard for QLoRA |
| Warmup ratio | 0.1 | |
| Epochs | 3 | |
| Optimizer | adamw_8bit | |
| Total steps | 243 | (1,289 / 16) × 3 |
| Training speed | ~1.7s/step | ~7 min total on A10G |
| Loss at step 72 | 0.1008 | Good — converged fast |

---

## 2. What Went Right

### Model Selection
- Qwen2.5-Coder-7B passed **7/7 sanity checks** for DuckDB SQL generation
- GGUF Q4_K_M quantization (4.4 GB) fits in HF Spaces free tier
- Good at code/SQL tasks out of the box

### Architecture
- Modular codebase: app.py / data_engine.py / model_inference.py / prompts.py
- Clean separation of concerns
- 81 tests passing

### Synthetic Data Generation
- Template-based approach works well for narrow domains
- 32 templates with weighted sampling
- Questions are parameterized (school names, years, thresholds) for variety
- Dedup prevents exact duplicate questions
- Each template generates matched Q/S pairs — no hallucinated SQL

### Training Execution
- Unsloth provides 2x speedup + 50% VRAM reduction
- Training converged fast (loss 0.1008 by step 72/243)
- QLoRA at 0.53% trainable params = cheap, fast, effective

### Key Fix: Fire-and-Forget via deploy + spawn
- **Problem:** 5 training runs crashed because `modal run` keeps a client connection open. When the local CLI times out or disconnects, Modal cancels the running function. `--detach` didn't help because cancellation arrives before detach.
- **Solution:** `modal deploy` creates a persistent app with zero client connection. Call `fn.spawn()` from Python — truly fire-and-forget.
- **Result:** Training completed all 3 epochs (243 steps), loss converged to 0.07.
- **EXACT COMMANDS USED:**
```bash
modal deploy modal_train/modal_app.py
python3 -c "
import modal
fn = modal.Function.from_name('kasualdad-lfed-train', 'run_full_pipeline')
fn.spawn()
"

---

## 3. What Went Wrong — Complete Error Catalog

### CRITICAL: Training Client Disconnects (⚠️ 5 runs crashed)
- **Symptom:** Training ran ~20-130 steps, then stopped with `Received a cancellation signal`
- **Root cause:** `modal run` keeps a gRPC connection. When local terminal exits (timeout, sleep, Ctrl+C), Modal cancels the remote function. `--detach` delay-implies detachment — the cancellation signal arrives before detach takes effect.
- **Fix:** `modal deploy` + call `fn.spawn()` from Python. Spawn fires with no client connection — the function runs to completion independently.
- **Commands:**
```bash
modal deploy modal_train/modal_app.py
python3 -c "
import modal
fn = modal.Function.from_name('kasualdad-lfed-train', 'export_and_push')
fn.spawn()
"
```
- **Lesson for future training runs:** NEVER use `modal run` for GPU work >60 seconds. ALWAYS deploy + spawn.

### CRITICAL: Files Not Available in Container (2 crashes)
- **Symptom:** `FileNotFoundError: '/root/generate_synthetic.py'` — only `modal_app.py` was uploaded.
- **Root cause:** Modal only uploads the entry-point file. Sibling scripts must be explicitly mounted.
- **Fix:** Add `.add_local_dir()` to the Modal image definition:
```python
train_image = modal.Image.debian_slim(...)
    .add_local_dir(Path(__file__).parent, remote_path="/root")
```
- **Failed attempts:** `modal.Mount` (deprecated, doesn't exist in v1.4.3), `condition=` kwarg (not supported on `add_local_dir`)

### CRITICAL: Cross-Device Link Error
- **Symptom:** `OSError: [Errno 18] Invalid cross-device link: '/root/train.jsonl' -> '/data/train.jsonl'`
- **Root cause:** `Path.rename()` / `os.rename()` fails across mount points (root mount ≠ volume mount)
- **Fix:** Use `shutil.move()` instead of `.rename()`

### CRITICAL: Pickle Error on Model Save (2 crashes)
- **Symptom:** `PicklingError: Can't pickle <class 'trl.trainer.sft_config.SFTConfig'>`
- **Root cause:** SFTTrainer calls `save_model()` which tries to pickle training args. SFTConfig from nested module can't be pickled.
- **Fix (3 layers):**
  1. `save_strategy="no"` — prevent auto-saves during training
  2. `try/except` around `trainer.train()` to catch pickle errors
  3. Manual save: `model.save_pretrained()` directly (bypasses trainer)

### CRITICAL: CUDA Out of Memory During Merge/Export (3 crashes)
- **Symptom:** `torch.OutOfMemoryError: Tried to allocate 14.23 GiB` during `load_adapter()`
- **Root cause:** Training leaves model in GPU. Loading 16-bit base model for merge needs 14GB, exceeding A10G 22GB when combined.
- **Fix:**
  1. Free GPU after training: `del model; gc.collect(); torch.cuda.empty_cache()`
  2. Run `export_and_push` via `.remote()` not `.local()` — fresh container with clean GPU
- **Failed attempts:** `load_in_4bit=True` + `merge_and_unload()` (NotImplementedError on quantized models)

### CRITICAL: merge_and_unload() Not Implemented
- **Symptom:** `NotImplementedError` when calling `merge_and_unload()` on quantized PEFT model
- **Fix:** Load base model in FP16 via `AutoModelForCausalLM`, then apply adapter via `PeftModel.from_pretrained(base_model, adapter_path)`, THEN merge. The key insight: load base in FP16 first, apply adapter separately.
```python
base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.float16)
model = PeftModel.from_pretrained(base_model, str(LORA_DIR))
model = model.merge_and_unload()
```

### GGUF Conversion: Missing Module (3 crashes)
- **Symptom:** `No module named 'llama_cpp.convert'`
- **Root cause:** llama-cpp-python doesn't have a built-in converter
- **Fix:** Clone llama.cpp repo + install `gguf` package. Use `convert_hf_to_gguf.py` from the repo.
- **Failed attempts:** Downloading single converter file (needs companion modules), `pip install gguf` in image (not picked up by cached image)

### Quantization: llama-quantize Missing (2 attempts)
- **Symptom:** `llama-quantize not found, using FP16 GGUF` → 15.2 GB model
- **Root cause:** llama.cpp quantize binary not built
- **Fix:** `llama_quantize()` from llama-cpp-python (v0.3.26+ has it built-in)
```python
from llama_cpp import llama_quantize
llama_quantize(input_path=f16_gguf, output_path=q4_gguf, output_type="q4_k_m")
```
- **Failed attempts:** cmake build (dependency issues, `-j$(nproc)` shell expansion fails with subprocess)

### HF Repo Push: Namespace Permission Error
- **Symptom:** `403 Forbidden: You don't have the rights to create a model under the namespace "kasualdad"`
- **Root cause:** HF API is case-sensitive. `kasualdad` ≠ `Kasualdad`. The token belongs to user `Kasualdad`.
- **Fix:** Use correct case: `HF_USERNAME = "Kasualdad"`

### Fine-Tuned Model Outputs Nothing (0 chars)
- **Symptom:** Model loads but generates 0 tokens for every query
- **Root cause:** Training used Qwen2.5 chat template (`<|im_start|>system...<|im_end|>`), but inference sent plain text. Model doesn't recognize the format.
- **Fix:** Update `build_prompt()` in `prompts.py` to use Qwen2.5 chat template:
```python
prompt = (
    f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
    f"<|im_start|>user\nQuestion: {question}<|im_end|>\n"
    f"<|im_start|>assistant\n"
)
```
- **Also:** Add `<|im_end|>` and `<|im_start|>` to stop sequences in `model_inference.py`

### CUDA Wheel on CPU Spaces
- **Symptom:** `libcuda.so.1: cannot open shared object file` on CPU Space
- **Root cause:** `requirements.txt` had `--extra-index-url cu121` which installs CUDA-linked llama-cpp-python
- **Fix:** Remove the CUDA wheel index. Standard PyPI wheel works on CPU + GPU.

### Local Dev: Missing spaces Module
- **Symptom:** `ModuleNotFoundError: No module named 'spaces'` when running locally
- **Root cause:** `spaces` is an HF infrastructure-only package
- **Fix:** Try/except import with no-op fallback:
```python
try:
    import spaces
    _gpu_decorator = spaces.GPU
except ImportError:
    _gpu_decorator = lambda fn: fn
```

### HF Space: Zero GPU Daily Limit
- **Symptom:** "You've hit your daily Zero GPU limit"
- **Root cause:** Free tier has limited daily GPU quota
- **Workaround:** Switch Space hardware to CPU (model still works, just slower)
- **Alternative:** $9/month PRO account for 8x quota

### Volume Cache Serves Stale Files
- **Symptom:** Code changes don't take effect, old errors repeat
- **Root cause:** Modal volumes persist `.pyc` files from old runs. `import` picks up cached bytecode.
- **Fix:** Clear module cache before importing:
```python
for key in list(sys.modules.keys()):
    if "script_name" in key:
        del sys.modules[key]
importlib.reload(module)
```

---

## 4. Post-Training Checklist (VERIFIED WORKING)

```bash
# 1. Verify GGUF pushed to Hub
# Check https://huggingface.co/build-small-hackathon/lfed-qwen2.5-coder-7b-sql-gguf
from huggingface_hub import HfApi
api = HfApi(token='hf_...')
for f in api.list_repo_tree('build-small-hackathon/lfed-qwen2.5-coder-7b-sql-gguf'):
    print(f'  {f.path} ({f.size/1e9:.2f} GB)')
# Expected: lfed-qwen2.5-coder-7b-sql-Q4_K_M.gguf (4.68 GB)

# 2. Update model_inference.py
# Set lines 101-102:
#   HF_REPO_ID = "build-small-hackathon/lfed-qwen2.5-coder-7b-sql-gguf"
#   HF_MODEL_FILE = "lfed-qwen2.5-coder-7b-sql-Q4_K_M.gguf"

# 3. Fix prompts.py: Qwen2.5 chat template (see Issue "Outputs Nothing")
#   MUST use <|im_start|>system/user/assistant<|im_end|> format

# 4. Fix model_inference.py stop sequences:
#   STOP_SEQUENCES = ["\n\n", "Question:", "User:", "<|im_end|>", "<|im_start|>"]

# 5. Fix app.py: spaces.GPU made optional for local dev
#   try/except ImportError with lambda:fn fallback

# 6. Test locally
cd Kasualdad_LFED && source .venv/bin/activate
python -c "
from model_inference import load_model, generate_sql
from data_engine import create_session, execute_safe
llm = load_model()  # downloads Q4_K_M from Hub (~3s on Mac)
raw, _ = generate_sql('How many students were chronically absent in 2023-2024?', llm=llm)
conn = create_session()
sql, df = execute_safe(conn, raw)
print(df)  # Should show: chronic_count = 435
"

# 7. Run tests
pytest tests/ -v

# 8. Commit + push to Space
git add -A && git commit -m "feat: fine-tuned Q4_K_M model" && git push space main

# 9. Verify Space
# Open https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED
# Click first example query — should return 435
```

---

## 6. Verified Results (2026-06-08)

### Training
| Metric | Value |
|---|---|
| Model | Qwen2.5-Coder-7B-Instruct → QLoRA fine-tuned |
| Training data | 1,289 NL→SQL pairs, 32 templates |
| Epochs | 3 (243 steps) |
| Final loss | 0.07 (converged from 2.6) |
| Training time | ~7 minutes on A10G |
| GGUF output | Q4_K_M, 4.68 GB |

### Inference (3/3 test queries pass)
| Query | SQL | Result |
|---|---|---|
| "How many students were chronically absent in 2023-2024?" | `SELECT COUNT(*) ... WHERE is_chronically_absent = TRUE` | **435** ✅ |
| "Show total enrollment per school for 2024-2025, sorted highest first." | `SELECT school_name, SUM(student_count) ... ORDER BY total_enrollment DESC` | Correct ranking ✅ |
| "What percentage of students at Lincoln Elementary were chronically absent?" | `ROUND(COUNT(CASE WHEN ...) * 100.0 / COUNT(*), 1)` | **13.7%** ✅ |

### Deployed URLs
- **HF Space:** https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED
- **Model repo:** https://huggingface.co/build-small-hackathon/lfed-qwen2.5-coder-7b-sql-gguf
- **Modal app:** https://modal.com/apps/flucido/main/deployed/kasualdad-lfed-train

```bash
# 1. Clone
cd /Users/flucido/projects/build-small-hackathon
# (or clone from HF: git clone https://huggingface.co/spaces/build-small-hackathon/Kasualdad_LFED)

# 2. Setup
cd Kasualdad_LFED
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
modal token set  # authenticate

# 3. Create HF secret for Modal
modal secret create huggingface HF_TOKEN=$(cat ~/.huggingface/token)

# 4. Run training
modal deploy modal_train/modal_app.py
# (use deploy, not run — see Issue 1 above)

# 5. Monitor
modal app list
modal app logs <app-id>
```
