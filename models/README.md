# Local Model Artifacts

Model weights are NOT committed to git. Fetch them from Hugging Face Hub into this directory.

## LFM3 two-hop (desktop)

The desktop host loads the calibrated Q8_0 GGUF through a loopback `llama-server`.

**HF repo:** `KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`
**File:** `lfed-lfm3-1.7b-two-hop-Q8_0.gguf`
**Size:** ~1.8 GB

```bash
# From repo root
hf download KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf \
  lfed-lfm3-1.7b-two-hop-Q8_0.gguf --local-dir models
```

The bf16 training checkpoint is published separately at
`KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`; the GGUF export job downloads it, so
you do not need it for desktop inference.

## lora-warehouse-r64 (legacy Gradio)

Trained on the real warehouse schema (main_core, main_analytics, main_staging — ~30+ tables).
Rank 64, alpha 64, all linear layers. This is the single-hop Qwen adapter; it
does not power the desktop two-hop path.

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

### Previous version (r=32)

The original adapter trained on synthetic 5-table data lives at:
`KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora` (HF Hub)

It is kept as a rollback safety net. The new r=64 adapter is a separate
model, not a version bump — different training data, different schema.
