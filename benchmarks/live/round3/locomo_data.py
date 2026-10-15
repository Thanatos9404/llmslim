"""LoCoMo (snap-research/locomo, data/locomo10.json) as every arm in round 3 sees it.

Turns are rendered the way Mem0's own harness renders them (mem0ai/memory-benchmarks @4b61c5d,
benchmarks/locomo/run.py): "Speaker: text", with a shared photo described inline. Sessions are in date order.
Questions in categories 1-4 are scored; category 5 (adversarial, unanswerable) is excluded, as in Mem0's and
Zep's published LoCoMo results.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
SCORED = (1, 2, 3, 4)


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    dia_id: str


@dataclass(frozen=True)
class Session:
    key: str
    date: datetime
    turns: tuple[Turn, ...]
    raw_date: str = ""


@dataclass(frozen=True)
class Question:
    id: str
    conv: int
    category: int
    question: str
    answer: str
    evidence: tuple[str, ...]


def parse_date(text: str) -> datetime:
    """LoCoMo dates look like '1:56 pm on 8 May, 2023'."""
    return datetime.strptime(text.strip(), "%I:%M %p on %d %B, %Y")


def turn_text(turn: dict) -> str:
    text = turn.get("text", "") or ""
    blip, query = turn.get("blip_caption", ""), turn.get("query", "")
    if query and blip:
        tag = f"[Sharing image - query: {query}. The image shows: {blip}]"
    elif query:
        tag = f"[Sharing image - query for: {query}]"
    elif blip:
        tag = f"[Sharing image that shows: {blip}]"
    else:
        tag = ""
    return f"{text} {tag}".strip() if tag else text


def load(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sessions(conversation: dict) -> list[Session]:
    conv = conversation["conversation"]
    keys = [k for k in conv if re.fullmatch(r"session_\d+", k) and conv[k]]
    out = []
    for key in keys:
        turns = tuple(
            Turn(t["speaker"], turn_text(t), t.get("dia_id", "")) for t in conv[key] if turn_text(t)
        )
        raw = conv[f"{key}_date_time"]
        out.append(Session(key, parse_date(raw), turns, raw))
    return sorted(out, key=lambda s: (s.date, int(s.key.split("_")[1])))


def speakers(conversation: dict) -> tuple[str, str]:
    return conversation["conversation"]["speaker_a"], conversation["conversation"]["speaker_b"]


def questions(data: list[dict], categories=SCORED) -> list[Question]:
    out = []
    for conv_index, conversation in enumerate(data):
        for q_index, qa in enumerate(conversation["qa"]):
            category = int(qa.get("category", 0))
            if category not in categories:
                continue
            answer = qa.get("answer", qa.get("adversarial_answer", ""))
            if category == 3 and isinstance(answer, str) and ";" in answer:
                answer = answer.split(";")[
                    0
                ].strip()  # Mem0's harness: open-domain keeps the first part
            out.append(
                Question(
                    f"c{conv_index}q{q_index}",
                    conv_index,
                    category,
                    qa["question"],
                    str(answer),
                    tuple(qa.get("evidence", [])),
                )
            )
    return out


def reference_date(conversation: dict) -> str:
    """The last session's date string, which Mem0's harness passes to its answer prompt for temporal grounding."""
    return sessions(conversation)[-1].raw_date


def transcript(conversation: dict) -> list[tuple[Session, list[str]]]:
    """Each session with its lines, 'Speaker: text', for the context-based arms."""
    return [(s, [f"{t.speaker}: {t.text}" for t in s.turns]) for s in sessions(conversation)]
