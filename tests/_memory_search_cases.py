"""Deterministic histories and searches for tests/test_memory_explain.py.

Every turn gets a fixed id (``m0001``, ``m0002``, ...) and a fixed time, so a search's whole output, ids included, is
the same on every run. The output of each case with ``explain`` off is pinned in
``tests/fixtures/memory_search_golden.json``, recorded from ``Memory.search`` before it had an ``explain`` argument,
with tiktoken's ``cl100k_base`` and the built-in sentence splitter. If a release changes what search selects on
purpose, regenerate it and say so in the CHANGELOG::

    python -m tests._memory_search_cases
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from llmslim.memory import InMemoryStore, Memory, MemoryContext, MemoryItem, MemoryStore

T0 = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "memory_search_golden.json"


class History:
    """A :class:`Memory` whose turns get fixed ids and times."""

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self.memory = Memory(store if store is not None else InMemoryStore())
        self.count = 0

    def say(
        self,
        role: str,
        content: str,
        *,
        day: int = 0,
        minutes: int = 0,
        user: str = "u1",
        run: Optional[str] = None,
    ) -> str:
        self.count += 1
        item = MemoryItem(
            id=f"m{self.count:04d}",
            role=role,
            content=content,
            created_at=T0 + timedelta(days=day, minutes=minutes),
            user_id=user,
            run_id=run,
        )
        self.memory.store.add([item])
        return item.id

    def chat(
        self,
        day: int,
        user: str,
        reply: str,
        *,
        minutes: int = 0,
        uid: str = "u1",
        run: Optional[str] = None,
    ) -> Tuple[str, str]:
        asked = self.say("user", user, day=day, minutes=minutes, user=uid, run=run)
        answered = self.say("assistant", reply, day=day, minutes=minutes, user=uid, run=run)
        return asked, answered


# ---------------------------------------------------------------- histories


def empty(store: Optional[MemoryStore] = None) -> History:
    return History(store)


def short_chat(store: Optional[MemoryStore] = None) -> History:
    history = History(store)
    history.chat(0, "My dog is called Bruno.", "What a good name!")
    return history


def lentils(store: Optional[MemoryStore] = None) -> History:
    """Forty days of near-identical dinner chat, then one turn that holds an address."""
    history = History(store)
    for day in range(40):
        history.chat(
            day,
            f"Day {day}: can you suggest a recipe with lentils and rice for dinner tonight?",
            f"Day {day}: try a simple khichdi with ghee, cumin and a side of pickle.",
        )
    history.chat(
        41,
        "By the way, I moved to 14 Lane 5, Koregaon Park, Pune last month.",
        "Thanks, I have noted your new address in Koregaon Park.",
    )
    return history


def _filler(history: History, days: int) -> None:
    """Long replies that repeat the user's words."""
    for day in range(days):
        history.chat(
            day,
            f"Day {day}: what should I cook for dinner with lentils and rice?",
            f"For dinner on day {day}, lentils and rice make a great khichdi. "
            + " ".join(
                f"Tip {k}: rinse the lentils and rice well before cooking dinner."
                for k in range(12)
            ),
        )


def triangle_request(store: Optional[MemoryStore] = None) -> History:
    history = lentils(store)
    history.chat(
        3,
        "Always include comparative analysis of multiple solution methods when I ask about "
        "triangle area.",
        "Understood.",
        minutes=5,
    )
    return history


def dinner_preferences(store: Optional[MemoryStore] = None) -> History:
    """Preferences (one said twice), standing requests, and a turn that is both."""
    history = History(store)
    _filler(history, 24)
    history.chat(3, "I prefer vegetarian meals that take under 20 minutes.", "Got it.", minutes=5)
    history.chat(5, "I usually shop at the farmers market on Saturdays.", "Nice.", minutes=5)
    history.chat(
        7,
        "Always keep dinner suggestions under 500 calories. I prefer spicy food.",
        "Will do.",
        minutes=5,
    )
    history.chat(9, "From now on, always give prices in rupees.", "Sure.", minutes=5)
    history.chat(15, "I prefer vegetarian meals that take under 20 minutes.", "Noted.", minutes=5)
    return history


def skydiving(store: Optional[MemoryStore] = None) -> History:
    """Statements that disagree: one says it happened, a later one denies it."""
    history = History(store)
    _filler(history, 20)
    history.chat(
        4,
        "I went skydiving over the Dubai desert with my cousin last spring.",
        "Wow!",
        minutes=5,
    )
    history.chat(
        12, "I have never gone skydiving, heights scare me too much.", "Understood.", minutes=5
    )
    return history


def moved(store: Optional[MemoryStore] = None) -> History:
    """A fact that changed: the older turn is not reconciled away."""
    history = History(store)
    _filler(history, 16)
    history.chat(2, "I live in Delhi, near Lodhi Garden.", "Lovely area.", minutes=5)
    history.chat(
        14, "I moved to Pune last month, so I no longer live in Delhi.", "Noted.", minutes=5
    )
    return history


def _thesis(store: Optional[MemoryStore], days: int) -> History:
    history = History(store)
    chatter = " ".join(
        f"Side note {k}: the weather was mild and the train ran late again." for k in range(12)
    )
    code = "```python\nimport pandas as pd\nflows = pd.read_csv('river.csv')\n```"
    for day in range(days):
        history.chat(
            day,
            f"Day {day}: today I finished chapter {day} of my thesis on river ecology. {code}",
            f"Great question! For chapter {day} of your thesis, keep the sediment section short. "
            f"{code} {chatter}\n\n1. **Lead with the sediment data**: it is the core.\n"
            f"2. **Keep chapter {day} under ten pages**: examiners skim.",
        )
    history.say("system", "The user writes in British English.", day=days)
    return history


def thesis(store: Optional[MemoryStore] = None) -> History:
    return _thesis(store, 12)


def long_thesis(store: Optional[MemoryStore] = None) -> History:
    return _thesis(store, 40)


def chinese(store: Optional[MemoryStore] = None) -> History:
    history = History(store)
    for day in range(12):
        history.chat(day, f"第{day}天：今天天气很好，我们去公园散步了。", "听起来很不错！")
    history.chat(13, "我的猫叫小白，它今年三岁了。", "小白是个好名字。")
    history.chat(14, "Я живу в Москве, но мой кот живёт у бабушки.", "Понятно.")
    return history


def huge(store: Optional[MemoryStore] = None) -> History:
    """One user turn and one reply, each far larger than the budgets they are searched with."""
    history = History(store)
    story = " ".join(
        f"On trip {k} we drove to a new town and stayed in a small hotel by the river."
        for k in range(80)
    )
    history.say("user", f"{story} My locker code at the gym is 4417. {story}")
    steps = "\n".join(f"{k}. Set option {k} in the config file and restart." for k in range(60))
    table = "| setting | value |\n|---|---|\n" + "\n".join(f"| key{k} | {k} |" for k in range(30))
    history.say(
        "assistant",
        f"To configure the cache, edit cache.toml.\n\n{steps}\n\n```toml\n[cache]\nsize = 512\n"
        f"ttl = 60\n```\n\n{table}\n\nThe cache warms up in about a minute.",
    )
    return history


def duplicates(store: Optional[MemoryStore] = None) -> History:
    history = History(store)
    for day in range(10):
        history.say("user", f"Note {day}: the plants on the balcony need water.", day=day)
    history.say("user", "I live in Pune, in Koregaon Park.", day=11)
    history.say("user", "I live in Pune, in Koregaon Park.", day=12)
    history.say("user", "i live in pune, in koregaon park!", day=13)
    return history


def ties(store: Optional[MemoryStore] = None) -> History:
    """Notes that score the same for the question: only their dates tell them apart."""
    history = History(store)
    for day in range(8):
        history.say("user", "The weekly meeting is in room 101.", day=day, minutes=day)
        history.say("user", f"Lunch on day {day} was soup.", day=day, minutes=day + 1)
    return history


def windowed(store: Optional[MemoryStore] = None) -> History:
    history = History(store)
    for day in range(10):
        history.chat(
            day,
            f"Day {day}: the meeting room for project {day} is room {day + 100}.",
            "Got it.",
        )
    return history


def people(store: Optional[MemoryStore] = None) -> History:
    """Two users, each with sessions of their own (a run, and turns grouped by day)."""
    history = History(store)
    for day in range(6):
        history.chat(
            day, f"Day {day}: my favourite colour is still green.", "Green it is.", uid="asha"
        )
        history.chat(day, f"Day {day}: my favourite colour is blue.", "Blue it is.", uid="ravi")
    history.chat(7, "Today I painted the fence green.", "Nice.", uid="asha", run="r1")
    history.chat(8, "My favourite colour is now teal.", "Teal, noted.", uid="asha", run="r2")
    history.chat(8, "Tomorrow I paint the door teal too.", "Good plan.", uid="asha", run="r2")
    return history


def prefers_soup(query: str, texts: Sequence[str]) -> List[float]:
    """A custom scorer that likes soup and nothing else."""
    return [1.0 if "soup" in text else 0.0 for text in texts]


# ---------------------------------------------------------------- searches

Case = Tuple[str, Callable[..., History], str, Dict[str, Any]]

CASES: List[Case] = [
    ("empty", empty, "What did I say?", {"user_id": "u1"}),
    ("fits", short_chat, "What is my dog called?", {"user_id": "u1", "budget": 500}),
    ("lookup", lentils, "Where did I move to?", {"user_id": "u1", "budget": 200}),
    ("lookup_budget_1", lentils, "Where did I move to?", {"user_id": "u1", "budget": 1}),
    ("lookup_budget_12", lentils, "Where did I move to?", {"user_id": "u1", "budget": 12}),
    ("lookup_budget_40", lentils, "Where did I move to?", {"user_id": "u1", "budget": 40}),
    (
        "requests",
        triangle_request,
        "How do I find the area of a triangle from its medians?",
        {"user_id": "u1", "budget": 200},
    ),
    (
        "advice",
        dinner_preferences,
        "Can you suggest a quick dinner for tonight?",
        {"user_id": "u1", "budget": 400},
    ),
    (
        "advice_sections_off",
        dinner_preferences,
        "Can you suggest a quick dinner for tonight?",
        {"user_id": "u1", "budget": 400, "standing_requests": False, "preferences": False},
    ),
    ("conflicts", skydiving, "Have I ever gone skydiving?", {"user_id": "u1", "budget": 300}),
    ("conflicts_small", skydiving, "Have I ever gone skydiving?", {"user_id": "u1", "budget": 50}),
    ("moved", moved, "Have I ever lived in Delhi?", {"user_id": "u1", "budget": 300}),
    ("moved_lookup", moved, "Where do I live now?", {"user_id": "u1", "budget": 120}),
    (
        "summary",
        thesis,
        "Can you summarize what we discussed about my thesis?",
        {"user_id": "u1", "budget": 1200},
    ),
    (
        "summary_small",
        long_thesis,
        "Summarize my thesis progress",
        {"user_id": "u1", "budget": 150},
    ),
    (
        "summary_detail",
        long_thesis,
        "Can you summarize what we discussed about my thesis?",
        {"user_id": "u1", "budget": 5000},
    ),
    (
        "ordering",
        thesis,
        "In what order did I finish the chapters of my thesis?",
        {"user_id": "u1", "budget": 400},
    ),
    (
        "coverage_never",
        thesis,
        "Can you summarize what we discussed about my thesis?",
        {"user_id": "u1", "budget": 400, "coverage": "never"},
    ),
    ("chinese", chinese, "我的猫叫什么名字？", {"user_id": "u1", "budget": 60}),
    ("russian", chinese, "Где живёт мой кот?", {"user_id": "u1", "budget": 40}),
    ("huge_user", huge, "What is my locker code at the gym?", {"user_id": "u1", "budget": 150}),
    ("huge_reply", huge, "How do I configure the cache size?", {"user_id": "u1", "budget": 150}),
    ("huge_tiny", huge, "What is my locker code at the gym?", {"user_id": "u1", "budget": 9}),
    ("duplicates", duplicates, "Where do I live now?", {"user_id": "u1", "budget": 60}),
    ("ties", ties, "Which room is the weekly meeting in?", {"user_id": "u1", "budget": 40}),
    (
        "window",
        windowed,
        "Which room is project 5 in?",
        {
            "user_id": "u1",
            "budget": 60,
            "since": (T0 + timedelta(days=3)).isoformat(),
            "until": (T0 + timedelta(days=7)).isoformat(),
        },
    ),
    (
        "window_fits",
        windowed,
        "Which room is project 5 in?",
        {"user_id": "u1", "since": T0.isoformat(), "until": (T0 + timedelta(days=2)).isoformat()},
    ),
    ("people", people, "What is my favourite colour?", {"user_id": "asha", "budget": 60}),
    ("people_run", people, "What is my favourite colour?", {"user_id": "asha", "run_id": "r2"}),
    (
        "custom_scorer",
        ties,
        "What did I eat?",
        {"user_id": "u1", "budget": 30, "relevance": prefers_soup},
    ),
]


def run(case: Case, store: Optional[MemoryStore] = None, **extra: Any) -> MemoryContext:
    """The search of ``case`` on a fresh history in ``store``."""
    _, build, query, options = case
    return build(store).memory.search(query, **options, **extra)


def output(context: MemoryContext) -> Dict[str, Any]:
    """What a search returns, as JSON, without its timing (the only part that changes between runs)."""
    data = context.to_dict()
    data.pop("elapsed_ms")
    return data


def pinned(context: MemoryContext) -> Dict[str, Any]:
    """What the golden file keeps of a search: a SHA-256 of its whole output (every field of ``to_dict`` but
    ``elapsed_ms``, the turns' text and metadata included), and the parts worth reading when it differs."""
    data = output(context)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "text": data["text"],
        "tokens": data["tokens"],
        "turns": [[turn["id"], turn["partial"]] for turn in data["turns"]],
        "sections": {
            name: [turn["id"] for turn in data[name]]
            for name in ("requests", "preferences", "conflicts")
        },
    }


@contextlib.contextmanager
def builtin_splitter() -> Iterator[None]:
    """Sentences split by LLMSlim's own splitter, as on an installation without NLTK's punkt data."""
    from llmslim import tokenization
    from llmslim.memory import _turns

    saved = tokenization._NLTK_SPLIT, tokenization._NLTK_CHECKED
    tokenization._NLTK_SPLIT, tokenization._NLTK_CHECKED = None, True
    _turns.segments_of.cache_clear()
    try:
        yield
    finally:
        tokenization._NLTK_SPLIT, tokenization._NLTK_CHECKED = saved
        _turns.segments_of.cache_clear()


def write_golden() -> None:
    with builtin_splitter():
        golden = {case[0]: pinned(run(case)) for case in CASES}
    GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    from llmslim.tokens import get_active_token_counter_name

    if get_active_token_counter_name() != "tiktoken":
        raise SystemExit("the golden output is recorded with tiktoken: pip install tiktoken")
    write_golden()
    print(f"wrote {GOLDEN}")
