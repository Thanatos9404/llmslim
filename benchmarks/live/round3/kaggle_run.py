#!/usr/bin/env python3
"""Round-3 build runner for a cloud GPU (made for a public Kaggle notebook, 2x T4). It never calls the Claude API:
it only builds what each system would send to the reader, so anyone can rerun it and compare the outputs.

  setup    --work DIR               two pinned Python 3.12 environments: `main` (LLMSlim from this checkout,
                                    sentence-transformers) and `lingua` (LLMLingua 0.2.2 with transformers 4.44.2,
                                    which LongLLMLingua's KV-cache code needs)
  data     --work DIR               every dataset from its original source, checked against the sha256 below
  build    --work DIR --job NAME    one job from JOBS (resumable: finished cases are skipped)
  package  --work DIR --job NAME --zip FILE   manifest.json (commit, environment, GPU, data and output hashes,
                                    per-arm summaries) and a zip of the outputs

The repository is this file's own checkout (run it from a clone at the commit being tested).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

DATA = {  # path under WORK/data -> (url, sha256)
    "nq20/gold_at_0.jsonl.gz": (
        "https://raw.githubusercontent.com/nelson-liu/lost-in-the-middle/29b8a6d042ce29abccee3db1a73171a107d7e6af"
        "/qa_data/20_total_documents/nq-open-20_total_documents_gold_at_0.jsonl.gz",
        "69a8dd87a45f07fb3ed9b804917a89db975cd6e488682fc838edca029cc3881f",
    ),
    "nq20/gold_at_9.jsonl.gz": (
        "https://raw.githubusercontent.com/nelson-liu/lost-in-the-middle/29b8a6d042ce29abccee3db1a73171a107d7e6af"
        "/qa_data/20_total_documents/nq-open-20_total_documents_gold_at_9.jsonl.gz",
        "cbada411f70235afc47d9b5407e9358ad72eb021742402ff032c8b65076ffb2f",
    ),
    "nq20/gold_at_19.jsonl.gz": (
        "https://raw.githubusercontent.com/nelson-liu/lost-in-the-middle/29b8a6d042ce29abccee3db1a73171a107d7e6af"
        "/qa_data/20_total_documents/nq-open-20_total_documents_gold_at_19.jsonl.gz",
        "d79b715e1b8c8301335e93cb01659f68c24f0253a808c3190b06d21896506c6c",
    ),
    "hotpot_full/validation.parquet": (
        "https://huggingface.co/datasets/hotpotqa/hotpot_qa/resolve/main/distractor/validation-00000-of-00001.parquet",
        "c20b638ca82b21d04fe12e14ff417ad05153d4d215a65de54497fca4e972f7c6",
    ),
    "locomo/locomo10.json": (
        "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json",
        "79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4",
    ),
    "longmemeval/longmemeval_s_cleaned.json": (
        "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json",
        "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442",
    ),
}

TORCH = "torch==2.11.0+cu128"
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"
REQUIREMENTS = {  # the versions the local round-3 builds ran with
    "main": [
        "numpy==2.5.4",
        "scikit-learn==1.9.1",
        "jsonschema==4.26.0",
        "tiktoken==0.14.0",
        "sentence-transformers==6.1.0",
        "transformers==5.19.0",
        "pyarrow==26.0.0",
    ],
    "lingua": [
        "transformers==4.44.2",
        "accelerate==0.34.2",
        "llmlingua==0.2.2",
        "tokenizers==0.19.1",
        "safetensors==0.8.0",
        "huggingface-hub==0.36.2",
        "tiktoken==0.14.0",
        "nltk==3.10.3",
        "numpy==2.5.4",
        "scikit-learn==1.9.1",
        "jsonschema==4.26.0",
    ],
}

LOCOMO_BUDGETS = (1000, 2500, 10000)
V2_OFF = ("--off", "CHAINED_ROUNDS", "QUANTITY_TERMS")  # LLMSlim v3's switches that v2 did not have


def jobs(work: Path) -> dict[str, list[tuple[str, list[str]]]]:
    data, out = str(work / "data"), str(work / "out")
    rag = lambda suite, arms, *extra: [
        "build_rag.py",
        "--suite",
        suite,
        "--data",
        data,
        "--out",
        out,  # noqa: E731
        "--arms",
        *arms,
        *extra,
    ]
    locomo = lambda arms, budgets, *extra: [
        "build_locomo.py",
        "--data",
        f"{data}/locomo/locomo10.json",  # noqa: E731
        "--out",
        out,
        "--arms",
        *arms,
        "--budgets",
        *map(str, budgets),
        *extra,
    ]
    sample = str(work / "locomo_longlingua_sample.txt")
    lme = lambda arms, budgets: [
        "build_lme.py",
        "--data",
        f"{data}/longmemeval/longmemeval_s_cleaned.json",  # noqa: E731
        "--out",
        out,
        "--split",
        "test",
        "--arms",
        *arms,
        "--budgets",
        *map(str, budgets),
    ]
    return {
        # Everything except LongLLMLingua: a few hours on one T4.
        "main": [
            ("main", rag("nq", ["full", "order", "rerank", "llmslim", "llmslim_rr"])),
            ("main", rag("hotpot", ["full", "order", "rerank", "llmslim", "llmslim_rr"])),
            ("lingua", rag("nq", ["lingua2"])),
            ("lingua", rag("hotpot", ["lingua2"])),
            ("main", locomo(["full"], [0])),
            ("main", locomo(["recent"], [2500])),
            ("main", locomo(["rag", "llmslim", "llmslim_rr"], LOCOMO_BUDGETS)),
            ("lingua", locomo(["lingua2"], [2500, 10000])),
        ],
        # LongMemEval-S, 180 test questions (histories of about 115k tokens).
        "lme": [
            ("main", lme(["full"], [0])),
            ("main", lme(["recent", "rag", "llmslim", "llmslim_rr"], [2500, 10000])),
            ("lingua", lme(["lingua2"], [2500, 10000])),
        ],
        # The lme job ran out of GPU memory embedding long turns for the RAG arm (batches of 64); this reruns its
        # non-LLMSlim arms with smaller batches. LLMSlim's LongMemEval arms come from the llmslim_v23 job.
        "lme2": [
            ("main", lme(["full"], [0])),
            ("main", lme(["recent", "rag"], [2500, 10000])),
            ("lingua", lme(["lingua2"], [2500, 10000])),
        ],
        # LLMSlim after the round-3 change (#48, frozen before any test result was read), on the suites it changes.
        # NQ and HotpotQA output is identical to the release, so the main job's files stand for both.
        "llmslim_v2": [
            ("main", locomo(["llmslim", "llmslim_rr"], LOCOMO_BUDGETS, "--tag", "v2")),
            ("main", lme(["llmslim", "llmslim_rr"], [2500, 10000]) + ["--tag", "v2"]),
        ],
        # The llmslim_v2 job built everything but failed to package on a CPU machine (no nvidia-smi). This job
        # rebuilds those files and adds round 3's second change (#49, chosen on dev only). Both come from the same
        # code: v2 is v3 with #49's two switches off, which reproduces v2's output byte for byte.
        "llmslim_v23": [
            ("main", locomo(["llmslim"], LOCOMO_BUDGETS, "--tag", "v2", *V2_OFF)),
            ("main", locomo(["llmslim_rr"], [1000, 2500], "--tag", "v2", *V2_OFF)),
            ("main", lme(["llmslim", "llmslim_rr"], [2500, 10000]) + ["--tag", "v2", *V2_OFF]),
            ("main", locomo(["llmslim"], LOCOMO_BUDGETS, "--tag", "v3")),
            ("main", locomo(["llmslim_rr"], [1000, 2500], "--tag", "v3")),
            ("main", lme(["llmslim", "llmslim_rr"], [2500, 10000]) + ["--tag", "v3"]),
            ("main", rag("nq", ["llmslim", "llmslim_rr"], "--tag", "v3")),
            ("main", rag("hotpot", ["llmslim", "llmslim_rr"], "--tag", "v3")),
        ],
        # LongLLMLingua (LLaMA-2-7B-chat, fp16) on the pre-registered samples.
        "longlingua": [
            ("lingua", rag("nq", ["longlingua"], "--sample")),
            ("lingua", rag("hotpot", ["longlingua"], "--sample")),
            ("lingua", locomo(["longlingua"], [2500], "--ids", sample)),
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sh(cmd: list[str], env: dict | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def python(work: Path, name: str) -> str:
    return str(work / f"venv-{name}" / "bin" / "python")


def setup(work: Path) -> None:
    sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    for name, requirements in REQUIREMENTS.items():
        venv = work / f"venv-{name}"
        if not Path(python(work, name)).exists():
            try:
                sh(["uv", "venv", str(venv), "--python", "3.12", "-q"])
            except subprocess.CalledProcessError:
                sh(["uv", "venv", str(venv), "--python", sys.executable, "-q"])
        sh(
            [
                "uv",
                "pip",
                "install",
                "--python",
                python(work, name),
                "-q",
                TORCH,
                "--index-url",
                TORCH_INDEX,
            ]
        )
        sh(["uv", "pip", "install", "--python", python(work, name), "-q", *requirements])


def fetch(work: Path) -> None:
    for rel, (url, expected) in DATA.items():
        path = work / "data" / rel
        if path.exists() and sha256_file(path) == expected:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {rel}", flush=True)
        with urllib.request.urlopen(url, timeout=300) as response, path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        actual = sha256_file(path)
        if actual != expected:
            raise SystemExit(f"{rel}: sha256 {actual}, expected {expected}")
    json_path = work / "data" / "hotpot_full" / "validation.json"
    if not json_path.exists():
        sh(
            [
                python(work, "main"),
                "-c",
                "import json, pyarrow.parquet as pq, sys; "
                "json.dump(pq.read_table(sys.argv[1]).to_pylist(), open(sys.argv[2], 'w', encoding='utf-8'))",
                str(work / "data" / "hotpot_full" / "validation.parquet"),
                str(json_path),
            ]
        )
    splits = json.loads((HERE / "splits_r3.json").read_text())
    (work / "locomo_longlingua_sample.txt").write_text(
        "\n".join(splits["locomo"]["longlingua_sample"]) + "\n"
    )
    print("data ok", flush=True)


def build(work: Path, job: str) -> None:
    env = dict(
        os.environ,
        PYTHONPATH=str(REPO),
        HF_HOME=str(work / "hf"),
        PYTHONUNBUFFERED="1",
        PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True",
        TOKENIZERS_PARALLELISM="false",
        HF_HUB_DISABLE_PROGRESS_BARS="1",
        TRANSFORMERS_VERBOSITY="error",
        PYTHONIOENCODING="utf-8",
    )
    for name, args in jobs(work)[job]:
        started = time.time()
        sh([python(work, name), "-u", str(HERE / args[0]), *args[1:]], env)
        print(f"step took {(time.time() - started) / 60:.1f} min", flush=True)


def package(work: Path, job: str, zip_path: Path) -> None:
    out = work / "out"
    files = sorted(p for p in out.glob("*.jsonl"))
    summary = {}
    for path in files:
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        if rows:
            summary[path.name] = {
                "cases": len(rows),
                "mean_tokens": round(statistics.mean(r["tokens"] for r in rows), 1),
                "median_build_ms": round(statistics.median(r["build_ms"] for r in rows), 1),
            }
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    try:  # a CPU-only machine has no nvidia-smi
        gpus = (
            subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .splitlines()
        )
    except FileNotFoundError:
        gpus = []
    versions = {}
    for name in REQUIREMENTS:
        versions[name] = (
            subprocess.run(
                [python(work, name), "-m", "pip", "list", "--format=freeze"],
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            or subprocess.run(
                ["uv", "pip", "list", "--python", python(work, name), "--format=freeze"],
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )
    manifest = {
        "job": job,
        "commit": commit,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "gpus": gpus,
        "environments": versions,
        "data_sha256": {rel: expected for rel, (_, expected) in DATA.items()},
        "splits_r3_sha256": sha256_file(HERE / "splits_r3.json"),
        "outputs": {p.name: sha256_file(p) for p in files},
        "summary": summary,
    }
    (out / f"manifest-{job}.json").write_text(json.dumps(manifest, indent=1))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in [*files, out / f"manifest-{job}.json"]:
            archive.write(path, path.name)
    print(json.dumps(summary, indent=1))
    print(
        f"wrote {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB), sha256 {sha256_file(zip_path)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["setup", "data", "build", "package"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--job")
    parser.add_argument("--zip", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.step == "setup":
        setup(args.work)
    elif args.step == "data":
        fetch(args.work)
    elif args.step == "build":
        build(args.work, args.job)
    else:
        package(args.work, args.job, args.zip)


if __name__ == "__main__":
    main()
