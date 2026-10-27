"""
model_inference.py — Local SQL generation with pluggable backends.

Two backends, same call/response schema (llama_cpp.Llama-compatible):

  1. TransformersLLM  — transformers + PEFT (LoRA)
     - CUDA GPU: bnb-4bit base (~10 GB) + LoRA adapter
     - MPS/CPU:  fp16 base (~28 GB) + LoRA adapter

  2. LlamaCppLLM      — llama.cpp + GGUF (Q4_K_M, ~9 GB)
     - Apple Silicon (Metal) or CPU — the right choice for local Mac use
     - The GGUF already has the LoRA merged in (no adapter needed)

Backend selection (auto, override with LFED_BACKEND env var):
  - CUDA available  → transformers (bnb-4bit is fastest on GPU)
  - MPS / CPU       → llama.cpp GGUF (quantized, fits in 16 GB Macs)

The LoRA adapter (fp16 weights) applies to any transformers base precision.
The GGUF is a standalone merged model — the adapter is already baked in.

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

# Base models for the transformers backend — selected by device at load time.
# The bnb-4bit checkpoint is CUDA-only (bitsandbytes dequant requires CUDA).
# The fp16 base works on MPS (Apple Silicon) and CPU, at the cost of ~3x
# the memory footprint.
BASE_MODEL_4BIT = "unsloth/qwen2.5-coder-14b-instruct-bnb-4bit"
BASE_MODEL_FP16 = "Qwen/Qwen2.5-Coder-14B-Instruct"

# GGUF model for the llama.cpp backend (LoRA already merged in).
# Resolution order:
#   1. LFED_GGUF_PATH env var (explicit local path)
#   2. Local file models/lfed-qwen2.5-coder-14b-sql-warehouse-r64-Q4_K_M.gguf
#      (the warehouse r=64 merged GGUF — download from Modal volume)
#   3. HF Hub: KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf (old v1, 5-table schema)
GGUF_REPO = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf"
GGUF_FILENAME = "lfed-qwen2.5-coder-14b-sql-Q4_K_M.gguf"
_LOCAL_GGUF = str(
    Path(__file__).resolve().parent.parent
    / "models"
    / "lfed-qwen2.5-coder-14b-sql-warehouse-r64-Q4_K_M.gguf"
)


def _resolve_gguf_path() -> tuple[str | None, str | None]:
    """Return (local_path, repo_id) for the GGUF.

    If a local warehouse-r64 GGUF exists, use it (no HF download needed).
    Otherwise fall back to the HF Hub v1 GGUF.
    """
    env = os.environ.get("LFED_GGUF_PATH")
    if env and Path(env).exists():
        return env, None
    if Path(_LOCAL_GGUF).exists():
        return _LOCAL_GGUF, None
    return None, GGUF_REPO


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


def _resolve_base_model() -> str:
    """Pick the base model appropriate for the available accelerator.

    Priority:
      1. LFED_BASE_MODEL env var (explicit override — always wins)
      2. CUDA available → bnb-4bit (fast, ~10 GB)
      3. MPS available  → fp16 (~28 GB, Metal-accelerated)
      4. CPU only       → fp16 (slow, dev-only fallback)
    """
    env = os.environ.get("LFED_BASE_MODEL")
    if env:
        return env
    try:
        import torch

        if torch.cuda.is_available():
            return BASE_MODEL_4BIT
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return BASE_MODEL_FP16
    except Exception:
        pass
    return BASE_MODEL_FP16


def _resolve_backend() -> str:
    """Pick the inference backend.

    Priority:
      1. LFED_BACKEND env var ('transformers' | 'llamacpp')
      2. CUDA available → 'transformers' (bnb-4bit is fastest on GPU)
      3. MPS / CPU      → 'llamacpp' (GGUF is quantized, fits in 16 GB)
    """
    env = os.environ.get("LFED_BACKEND")
    if env in ("transformers", "llamacpp"):
        return env
    try:
        import torch

        if torch.cuda.is_available():
            return "transformers"
    except Exception:
        pass
    return "llamacpp"


# Keep the old name for backward compat (tests, env overrides)
BASE_MODEL_4BIT = os.environ.get("LFED_BASE_MODEL", BASE_MODEL_4BIT)

DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.0
STOP_SEQUENCES = ["\n\n", "Question:", "User:", "<|im_end|>", "<|im_start|>"]

# Thread-safe model cache
_lock = threading.Lock()
_llm: TransformersLLM | LlamaCppLLM | None = None


# ── Shared helpers ─────────────────────────────────────────────────────


def _truncate_on_stop(text: str, stop: list[str] | None) -> tuple[str, bool]:
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


# ── Transformers + PEFT backend ────────────────────────────────────────


class TransformersLLM:
    """Callable wrapper around transformers generate() that mimics the
    llama_cpp.Llama response schema used by the rest of the app."""

    def __init__(self, base_model: str | None = None, adapter: str = ADAPTER_REPO):
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if base_model is None:
            base_model = _resolve_base_model()

        self.torch = torch
        use_cuda = torch.cuda.is_available()
        use_mps = (
            not use_cuda
            and getattr(torch.backends, "mps", None)
            and torch.backends.mps.is_available()
        )
        device_label = "cuda" if use_cuda else ("mps" if use_mps else "cpu")
        print(f"🤖 Loading base model: {base_model} (device={device_label})")

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
        elif use_mps:
            # Apple Silicon: fp16 base on Metal. device_map="auto" doesn't
            # support MPS, so we load to CPU then move to MPS.
            load_kwargs["torch_dtype"] = torch.float16
        else:
            # CPU fallback — fp16 weights loaded in float32.
            load_kwargs["torch_dtype"] = torch.float32

        model = AutoModelForCausalLM.from_pretrained(base_model, **load_kwargs)

        if use_mps:
            model = model.to("mps")

        if adapter:
            print(f"🔗 Applying LoRA adapter: {adapter}")
            # torch_device="cpu": load adapter weights to CPU first. On
            # ZeroGPU, safetensors loading straight to cuda fails at startup
            # ("No CUDA GPUs are available") — copying CPU tensors into the
            # model's (emulated) CUDA params works fine.
            model = PeftModel.from_pretrained(model, adapter, torch_device="cpu")
            if use_mps:
                model = model.to("mps")

        model.eval()
        self.model = model

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
        text, _ = _truncate_on_stop(text, stop)
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


# ── llama.cpp + GGUF backend ───────────────────────────────────────────


class LlamaCppLLM:
    """llama.cpp wrapper with the same call/response schema as TransformersLLM.

    Loads a pre-merged GGUF (the LoRA adapter is already baked in, so no
    separate adapter load). Uses Metal on macOS (n_gpu_layers=-1) for
    GPU-accelerated inference on Apple Silicon.

    Prefers the local warehouse-r64 GGUF if present; falls back to the
    HF Hub v1 GGUF.
    """

    def __init__(self, repo_id: str = GGUF_REPO, filename: str = GGUF_FILENAME):
        from llama_cpp import Llama

        local_path, hf_repo = _resolve_gguf_path()

        if local_path:
            print(f"🤖 Loading local GGUF: {local_path}")
            model_path = local_path
        else:
            print(f"🤖 Loading GGUF from HF: {hf_repo}/{filename}")
            from huggingface_hub import hf_hub_download

            model_path = hf_hub_download(repo_id=hf_repo, filename=filename)

        # Detect Metal (MPS) for GPU layer offload
        n_gpu_layers = -1  # all layers on GPU; falls back to CPU if no Metal
        import platform

        is_mac = platform.system() == "Darwin"
        if not is_mac:
            n_gpu_layers = 0  # CPU-only on non-Mac without CUDA

        print(f"   n_gpu_layers={n_gpu_layers} ({'Metal' if is_mac else 'CPU'})")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=8192,
            n_gpu_layers=n_gpu_layers,
            n_threads=max(1, os.cpu_count() // 2) if not is_mac else 2,
            verbose=False,
        )

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

        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop or [],
            temperature=temperature,
            echo=echo,
        )
        text = response["choices"][0]["text"]
        text, _ = _truncate_on_stop(text, stop)
        return {"choices": [{"text": text}]}

    def _stream(
        self,
        prompt: str,
        max_tokens: int,
        stop: list[str] | None,
        temperature: float,
    ) -> Generator[dict, None, None]:
        for chunk in self.llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop or [],
            temperature=temperature,
            stream=True,
        ):
            text = chunk["choices"][0].get("text", "")
            if text:
                yield {"choices": [{"text": text}]}


# ── Model loading ──────────────────────────────────────────────────────


def load_model(verbose: bool = False) -> TransformersLLM | LlamaCppLLM:
    """Load the model. Thread-safe global singleton.

    Backend is auto-selected by device (override with LFED_BACKEND):
      - CUDA      → transformers + bnb-4bit + LoRA
      - MPS / CPU → llama.cpp + GGUF (Q4_K_M, ~9 GB, Metal-accelerated)
    """
    global _llm

    if _llm is not None:
        return _llm

    with _lock:
        if _llm is not None:  # Double-check after acquiring lock
            return _llm

        backend = _resolve_backend()
        t0 = time.time()
        print(f"🔧 Backend: {backend}")
        if backend == "llamacpp":
            _llm = LlamaCppLLM()
        else:
            _llm = TransformersLLM()
        print(f"✅ Model loaded in {time.time() - t0:.1f}s")
        return _llm


def get_model() -> TransformersLLM | LlamaCppLLM | None:
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
