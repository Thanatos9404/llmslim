"""Rebuild a sample of each built arm with the current Core source and check the prompts are identical."""

import json
import random
import sys

import bench2


def check(suite, arm, split="test_a", n=25):
    bench2.SPLIT["name"] = split
    path = bench2.BUILT / bench2.tag(suite) / f"{arm}.jsonl"
    if not path.exists():
        print(f"{suite}/{split}/{arm}: not built")
        return
    built = {
        json.loads(l)["id"]: json.loads(l)
        for l in path.read_bytes().decode("utf-8").split("\n")
        if l.strip()
    }
    items = {
        it["id"]: it
        for it in bench2.SUITES[suite]["load"]({"nq": 300, "lme": 90, "lbv2": 180}[suite])
    }
    ids = random.Random(1).sample(sorted(set(built) & set(items)), min(n, len(built)))
    same = sum(
        bench2._build_one((suite, arm, items[i]))["prompt"] == built[i]["prompt"] for i in ids
    )
    print(f"{suite}/{split}/{arm}: {same}/{len(ids)} identical")


for spec in sys.argv[1:]:
    check(*spec.split(":"))
