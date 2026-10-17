"""Replay real Claude Code transcripts at each model's own list rates (corrected: Opus 5.5 reads cache at 0.05x).

Same-trajectory analysis, in units of each request's base input price converted to dollars per model:
- the bill split into uncached input, cache writes, cache reads and output;
- the share of the bill by the request's prompt size;
- the cache-read cost of prompt tokens beyond 100k / 150k / 200k (what compacting at that size could at most remove);
- the ceiling for a compressor of shell/search/web output and of all tool output (if it cost nothing);
- what llmslim 0.11.1's proxy compression (JSON left alone, its default) would have removed.

Usage: replay_bill.py ROOT OUT_JSON [--no-proxy] [--before=ISO8601]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# USD per million tokens: (input, output, cache-read multiple). Writes: 1.25x (5-minute), 2x (1-hour).
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.05),
    "claude-opus-4-8": (5.0, 25.0, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.10),
}
COMPRESSIBLE = {"Bash", "PowerShell", "Grep", "Glob", "WebFetch", "WebSearch", "Monitor"}

root, out_path = Path(sys.argv[1]), Path(sys.argv[2])
with_proxy = "--no-proxy" not in sys.argv
CUTOFF = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--before=")), None)
if with_proxy:
    from llmslim.proxy.rewrite import Policy, _query, compress_output

    POLICY = Policy()


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        )
    return ""


def price(model):
    for key, value in PRICES.items():
        if model and model.startswith(key):
            return value
    return None


parts = defaultdict(float)
buckets = defaultdict(float)
beyond = defaultdict(float)
ceiling = defaultdict(float)
proxy_saved = 0.0
by_model = defaultdict(float)
unpriced = defaultdict(int)
seen_requests, seen_results = set(), set()
EDGES = [
    (50_000, "<50k"),
    (100_000, "50-100k"),
    (200_000, "100-200k"),
    (400_000, "200-400k"),
    (10**12, ">=400k"),
]

for path in sorted(f for f in root.rglob("*.jsonl") if "llmslim-wrap-e2e" not in str(f)):
    parsed = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if CUTOFF:
        parsed = [d for d in parsed if not d.get("timestamp") or d["timestamp"] < CUTOFF]
    final = {}
    for d in parsed:
        m = d.get("message")
        if (
            isinstance(m, dict)
            and d.get("type") == "assistant"
            and m.get("id")
            and isinstance(m.get("usage"), dict)
        ):
            final[m["id"]] = (m["usage"], m.get("model"))
    chains = {}
    if CUTOFF:
        parsed = [d for d in parsed if not d.get("timestamp") or d["timestamp"] < CUTOFF]
    for d in parsed:
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        key = (bool(d.get("isSidechain")), d.get("agentId") or "")
        st = chains.setdefault(
            key, {"calls": {}, "old": defaultdict(float), "new": defaultdict(float), "prev": 0}
        )
        content = m.get("content")
        if d.get("type") == "assistant":
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    st["calls"][b.get("id")] = (b.get("name"), b.get("input"))
            mid = m.get("id")
            if mid not in final or mid in seen_requests:
                continue
            seen_requests.add(mid)
            u, model = final[mid]
            p = price(model)
            if p is None:
                unpriced[model] += 1
                continue
            p_in, p_out, cr_mult = p
            cc = u.get("cache_creation") or {}
            one_h = cc.get("ephemeral_1h_input_tokens") or 0
            cw = u.get("cache_creation_input_tokens") or 0
            cr = u.get("cache_read_input_tokens") or 0
            inp = u.get("input_tokens") or 0
            out = u.get("output_tokens") or 0

            def usd(tokens, mult, price_in=p_in):
                return tokens * price_in * mult / 1e6

            cost = {
                "uncached input": usd(inp, 1),
                "cache writes": usd(cw - one_h, 1.25) + usd(one_h, 2),
                "cache reads": usd(cr, cr_mult),
                "output (incl. thinking)": out * p_out / 1e6,
            }
            for k, v in cost.items():
                parts[k] += v
            total = sum(cost.values())
            by_model[model] += total
            prompt = inp + cw + cr
            for edge, name in EDGES:
                if prompt < edge:
                    buckets[name] += total
                    break
            for cap in (100_000, 150_000, 200_000):
                if prompt > cap:
                    beyond[cap] += usd(prompt - cap, cr_mult)
            if not prompt:
                continue
            if st["prev"] and prompt < 0.5 * st["prev"]:
                st["old"].clear()
                st["new"].clear()
            st["prev"] = prompt
            write_mult = 2.0 if one_h > (cc.get("ephemeral_5m_input_tokens") or 0) else 1.25
            old_mult = cr_mult if cr >= 0.5 * prompt else write_mult
            for kind in ("compressible tools", "all tools", "proxy"):
                removed = min(st["old"][kind], prompt) * old_mult + st["new"][kind] * write_mult
                if kind == "proxy":
                    proxy_saved += usd(removed, 1)
                else:
                    ceiling[kind] += usd(removed, 1)
                st["old"][kind] += st["new"][kind]
                st["new"][kind] = 0
        elif d.get("type") == "user" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                tid = b.get("tool_use_id")
                if tid in seen_results:
                    continue
                seen_results.add(tid)
                text = text_of(b.get("content"))
                tool, tool_input = st["calls"].get(tid, ("?", None))
                tokens = len(text) / 4
                st["new"]["all tools"] += tokens
                if tool in COMPRESSIBLE:
                    st["new"]["compressible tools"] += tokens
                if with_proxy and len(text) >= 4000 and POLICY.eligible(tool):
                    result = compress_output(text, _query(tool_input), POLICY)
                    if result is not None:
                        st["new"]["proxy"] += result[1] - result[2]

total = sum(parts.values())
summary = {
    "requests": len(seen_requests),
    "unpriced_models": dict(unpriced),
    "total_usd_list": total,
    "by_model_usd": dict(by_model),
    "bill_split": {k: v / total for k, v in parts.items()},
    "by_prompt_size": {k: v / total for k, v in buckets.items()},
    "beyond_cap_share": {f"beyond_{k // 1000}k": v / total for k, v in beyond.items()},
    "ceiling_share": {k: v / total for k, v in ceiling.items()},
    "proxy_saved_share": proxy_saved / total if with_proxy else None,
}
out_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(json.dumps(summary, indent=1))
