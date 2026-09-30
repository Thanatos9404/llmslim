"""Small reproducible CPU sanity benchmark for real Transformers KV reuse.

Randomly initialized local weights are used; this checks computation and
latency, not language-model answer quality or a cloud provider cache.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import torch
from transformers import LlamaConfig, LlamaForCausalLM

from llmslim import TransformersKVSession

ROOT = Path(__file__).resolve().parents[1]


def run(trials: int = 10) -> dict[str, object]:
    torch.manual_seed(7)
    torch.set_num_threads(1)
    model = LlamaForCausalLM(LlamaConfig(vocab_size=256, hidden_size=64,
        intermediate_size=128, num_hidden_layers=2, num_attention_heads=4,
        num_key_value_heads=4, max_position_embeddings=512)).eval()
    tokenizer = object()
    prefix = [index % 254 + 1 for index in range(128)]
    full = prefix + [42]
    full_times: list[float] = []
    continuation_times: list[float] = []
    errors: list[float] = []
    identity = {"device": "cpu", "model_revision": "random-weights-seed-7",
                "tokenizer_revision": "integer-tokenizer-v1",
                "renderer_version": "raw-token-sequence-v1", "tenant_id": "offline-test"}
    # Warm model kernels outside the timed samples.
    with torch.no_grad():
        model(input_ids=torch.tensor([full]), use_cache=False)
    for _ in range(trials):
        session = TransformersKVSession(model=model, tokenizer=tokenizer, **{
            key: value for key, value in identity.items() if key != "device"})
        session.forward(full_token_ids=prefix, attention_mask=[1] * len(prefix),
            position_ids=list(range(len(prefix))), **identity)
        started = time.perf_counter()
        cached = session.forward(full_token_ids=full, attention_mask=[1] * len(full),
            position_ids=list(range(len(full))), **identity)
        continuation_times.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        with torch.no_grad():
            ordinary = model(input_ids=torch.tensor([full]), use_cache=False)
        full_times.append((time.perf_counter() - started) * 1000)
        errors.append(float(torch.max(torch.abs(cached.logits[:, -1] - ordinary.logits[:, -1]))))
    return {"classification": "MEASURED_LOCAL_CPU", "trials": trials,
            "model": "random two-layer Llama, hidden_size=64, 128-token prefix plus one token",
            "full_forward_median_ms": round(statistics.median(full_times), 4),
            "cached_continuation_median_ms": round(statistics.median(continuation_times), 4),
            "max_last_logit_absolute_error": round(max(errors), 8),
            "provider_calls": 0, "answer_quality_measured": False,
            "notes": "Prefill was performed before timing continuation. This is a tiny CPU model, not provider TTFT."}


if __name__ == "__main__":
    output = ROOT / "benchmarks" / "results" / "v0.7.1-local-kv.json"
    result = run()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
