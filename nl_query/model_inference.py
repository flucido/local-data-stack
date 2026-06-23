"""
model_inference.py — transformers + PEFT wrapper for local SQL generation.

ZeroGPU-compatible: uses PyTorch (transformers + bitsandbytes 4-bit), which is
the only CUDA path supported by HF Spaces ZeroGPU. The previous llama.cpp
backend could not access ZeroGPU's PyTorch-only CUDA emulation.

Model = pre-quantized 4-bit base (unsloth/qwen2.5-coder-14b-instruct-bnb-4bit)
      + LoRA adapter (KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64, r=64)

This is exactly the configuration the model was QLoRA fine-tuned in.

The loaded object (`TransformersLLM`) is callable with the same signature and
response schema as llama_cpp.Llama, so downstream code is backend-agnostic:

    out = llm(prompt, max_tokens=256, stop=[...], temperature=0.0)
    text = out["choices"][0]["text"]
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

from prompts import build_prompt

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

DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.0
STOP_SEQUENCES = ["\n\n", "Question:", "User:", "<|im_end|>", "<|im_start|>"]

# Thread-safe model cache
_lock = threading.Lock()
_llm: TransformersLLM | None = None


# ── llama.cpp-compatible wrapper ───────────────────────────────────────


class TransformersLLM:
    """Callable wrapper around transformers generate() that mimics the
    llama_cpp.Llama response schema used by the rest of the app."""

    def __init__(self, base_model: str = BASE_MODEL_4BIT, adapter: str = ADAPTER_REPO):
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        use_cuda = torch.cuda.is_available()
        print(f"🤖 Loading base model: {base_model} (cuda={use_cuda})")

        # Tokenizer comes from the adapter repo (carries the fine-tune's
        # chat template); falls back to the base model.
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(adapter)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(base_model)

        load_kwargs = {"low_cpu_mem_usage": True}
        if use_cuda:
            # Pre-quantized bnb-4bit checkpoint: no BitsAndBytesConfig needed.
            load_kwargs["device_map"] = "auto"
            load_kwargs["torch_dtype"] = torch.bfloat16
        else:
            # CPU/MPS dev fallback — bitsandbytes requires CUDA. Expect this
            # only with LFED_BASE_MODEL pointing at a small fp16 model.
            load_kwargs["torch_dtype"] = torch.float32

        model = AutoModelForCausalLM.from_pretrained(base_model, **load_kwargs)

        if adapter:
            print(f"🔗 Applying LoRA adapter: {adapter}")
            # torch_device="cpu": load adapter weights to CPU first. On
            # ZeroGPU, safetensors loading straight to cuda fails at startup
            # ("No CUDA GPUs are available") — copying CPU tensors into the
            # model's (emulated) CUDA params works fine.
            model = PeftModel.from_pretrained(model, adapter, torch_device="cpu")

        model.eval()
        self.model = model

    # -- helpers --------------------------------------------------------

    def _truncate_on_stop(self, text: str, stop: list[str] | None) -> tuple[str, bool]:
        if not stop:
            return text, False
        cut = len(text)
        hit = False
        for s in stop:
            idx = text.find(s)
            if idx != -1 and idx < cut:
                cut = idx
                hit = True
        return text[:cut], hit

    def _gen_kwargs(self, max_tokens: int, temperature: float) -> dict:
        kwargs = {
            "max_new_tokens": max_tokens,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
        }
        if temperature and temperature > 0:
            kwargs.update(do_sample=True, temperature=temperature)
        else:
            kwargs.update(do_sample=False)
        return kwargs

    # -- llama.cpp-style call -------------------------------------------

    def __call__(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stop: list[str] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        echo: bool = False,
        stream: bool = False,
    ):
        if stream:
            return self._stream(prompt, max_tokens, stop, temperature)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with self.torch.inference_mode():
            output_ids = self.model.generate(**inputs, **self._gen_kwargs(max_tokens, temperature))
        new_ids = output_ids[0][inputs["input_ids"].shape[1] :]
        text = self.tokenizer.decode(new_ids, skip_special_tokens=True)
        text, _ = self._truncate_on_stop(text, stop)
        return {"choices": [{"text": text}]}

    def _stream(
        self,
        prompt: str,
        max_tokens: int,
        stop: list[str] | None,
        temperature: float,
    ) -> Generator[dict, None, None]:
        from transformers import TextIteratorStreamer

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        kwargs = dict(inputs, streamer=streamer, **self._gen_kwargs(max_tokens, temperature))
        thread = threading.Thread(target=self.model.generate, kwargs=kwargs)
        thread.start()
        for piece in streamer:
            yield {"choices": [{"text": piece}]}
        thread.join()


# ── Model loading ──────────────────────────────────────────────────────


def load_model(verbose: bool = False) -> TransformersLLM:
    """Load the model (base 4-bit + LoRA). Thread-safe global singleton."""
    global _llm

    if _llm is not None:
        return _llm

    with _lock:
        if _llm is not None:  # Double-check after acquiring lock
            return _llm

        t0 = time.time()
        _llm = TransformersLLM()
        print(f"✅ Model loaded in {time.time() - t0:.1f}s")
        return _llm


def get_model() -> TransformersLLM | None:
    """Return the cached model, or None if not loaded."""
    return _llm


# ── SQL generation ─────────────────────────────────────────────────────


def generate_sql(
    user_question: str,
    llm=None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    schema: dict | None = None,
) -> tuple[str, str]:
    """
    Generate SQL from a natural-language question.

    Returns:
        (raw_output, prompt) tuple — raw_output may include ```sql``` wrapping.
    """
    if llm is None:
        llm = get_model()
        if llm is None:
            llm = load_model()

    prompt = build_prompt(user_question, schema=schema)

    t0 = time.time()
    response = llm(
        prompt,
        max_tokens=max_tokens,
        stop=STOP_SEQUENCES,
        temperature=temperature,
        echo=False,
    )
    elapsed = time.time() - t0
    raw_text = response["choices"][0]["text"]
    print(f"⚡ Generated in {elapsed:.1f}s ({len(raw_text)} chars)")

    return raw_text, prompt


def generate_sql_streaming(
    user_question: str,
    llm=None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    schema: dict | None = None,
) -> Generator[str, None, None]:
    """
    Stream SQL for real-time Gradio display. Yields the full accumulated
    text so far on each chunk; stops when a stop sequence appears.
    """
    if llm is None:
        llm = get_model()
        if llm is None:
            llm = load_model()

    prompt = build_prompt(user_question, schema=schema)

    stream = llm(
        prompt,
        max_tokens=max_tokens,
        stop=STOP_SEQUENCES,
        temperature=temperature,
        echo=False,
        stream=True,
    )

    accumulated = ""
    for chunk in stream:
        text = chunk["choices"][0].get("text", "")
        accumulated += text

        # Check accumulated text for stop sequences
        truncated = False
        for stop_seq in STOP_SEQUENCES:
            if stop_seq in accumulated:
                idx = accumulated.index(stop_seq)
                accumulated = accumulated[:idx]
                truncated = True
                break

        if accumulated:
            yield accumulated

        if truncated:
            return
