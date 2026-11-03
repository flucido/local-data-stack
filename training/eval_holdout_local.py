"""eval_holdout_local.py — Run the K-12 Two-Hop holdout eval locally against the fine-tuned LFM3 bf16 model.

Runs entirely on this machine (MPS/CPU) so no student warehouse data leaves the laptop.
Loads `KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16` (or a local path) with transformers and plugs it
into `nl_query.eval.run_eval(two_hop=True)` (Top-K pruning + Hop 1 + self-healing retries).

Usage:
    uv run --with transformers --with torch --with accelerate python training/eval_holdout_local.py \
        [--model KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Disable upper limit for MPS allocations on Apple Silicon unified memory
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nl_query"))


class LocalChatMLLLM:
    """Callable mimicking the llama_cpp / TransformersLLM response schema."""

    def __init__(self, model_id: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.is_available():
            device, dtype = "cuda", torch.bfloat16
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device, dtype = "mps", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32
        print(f"Loading {model_id} on {device} ({dtype})")
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, dtype=dtype, trust_remote_code=True
        ).to(device)
        self.model.eval()
        im_end = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
        self.eos_ids = [
            t for t in (im_end, self.tokenizer.eos_token_id) if isinstance(t, int) and t >= 0
        ]

    def __call__(
        self, prompt, max_tokens=256, stop=None, temperature=0.0, echo=False, stream=False
    ):
        inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(
            self.model.device
        )
        with self.torch.inference_mode():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.eos_ids or self.tokenizer.eos_token_id,
            )
        text = self.tokenizer.decode(
            out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=False
        )
        # Free accelerator memory between generations (MPS otherwise accumulates and OOMs mid-run)
        del out, inputs
        import gc

        gc.collect()
        if self.model.device.type == "mps":
            self.torch.mps.empty_cache()
        elif self.model.device.type == "cuda":
            self.torch.cuda.empty_cache()
        # Cut at ChatML end-of-turn; do NOT cut on "\n\n" (JSON tool calls may legitimately contain it)
        for s in ("<|im_end|>", "<|im_start|>"):
            if s in text:
                text = text.split(s)[0]
        return {"choices": [{"text": text.strip()}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16")
    ap.add_argument("--test-set", default=str(ROOT / "nl_query" / "eval_two_hop_holdout.jsonl"))
    ap.add_argument(
        "--warehouse", default=str(ROOT / "oss_framework" / "data" / "analytics.duckdb")
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=384)
    ap.add_argument("--out", default=str(ROOT / "training" / "holdout_results.json"))
    args = ap.parse_args()

    import eval as nl_eval
    import model_inference

    test_set = args.test_set
    if args.limit:
        rows = [
            json.loads(line) for line in Path(test_set).read_text().splitlines() if line.strip()
        ][: args.limit]
        tmp = ROOT / "training" / "_holdout_subset.jsonl"
        tmp.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        test_set = str(tmp)

    llm = LocalChatMLLLM(args.model)
    model_inference.load_model = lambda verbose=False: llm  # type: ignore[assignment]

    t0 = time.time()
    traces = str(ROOT / "training" / "holdout_traces.jsonl")
    result = nl_eval.run_eval(
        args.model,
        test_set,
        args.warehouse,
        max_tokens=args.max_tokens,
        traces_path=traces,
        two_hop=True,
        prune_k=5,
        max_retries=2,
    )
    summary = {
        "model": args.model,
        "total": result.total,
        "ex_at_1_first_pass": result.first_pass_hits,
        "ex_at_3_with_self_healing": result.execution_hits,
        "self_healed_hits": result.self_healed_hits,
        "exact_hits": result.exact_hits,
        "errors": result.errors,
        "hop2_ui_valid_hits": result.hop2_ui_valid_hits,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    os.environ.pop("LFED_ADAPTER_REPO", None)


if __name__ == "__main__":
    main()
