"""The session behind docs/assets/llmslim-memory-demo.svg: store chat turns, then recall them within a budget.

It seeds a SQLite file with a month of chat, then types a few lines into a real Python console (``code``), so every
line of output is printed by llmslim itself. Only the typing speed is set here. To record it again (Linux or WSL,
since asciinema needs a pty):

    uv venv .venv && uv pip install --python .venv/bin/python "llmslim[mcp]==0.11.1" asciinema==2.4.0
    .venv/bin/asciinema rec --cols 82 --rows 14 -c ".venv/bin/python memory_session.py" demo.cast
    npx svg-term-cli@2.1.1 --in demo.cast --out llmslim-memory-demo.svg --window --no-cursor
"""

from __future__ import annotations

import code
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from llmslim.memory import Memory

DB = "asha.db"
START = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)
SMALL_TALK = [
    (
        "Can you suggest something quick for dinner?",
        "Try a vegetable khichdi: rice, lentils, cumin and ghee.",
    ),
    (
        "How do I stop my plants from wilting in this heat?",
        "Water early in the morning and move them out of the sun.",
    ),
    (
        "Any podcast for my commute?",
        "If you like history, try a long-form series on the Mughal empire.",
    ),
    (
        "What should I pack for a weekend in Lonavala?",
        "A light rain jacket, walking shoes and a power bank.",
    ),
]
LINES = [
    "from llmslim.memory import Memory",
    'mem = Memory("asha.db")  # a month of chat with Asha is stored here',
    'len(mem.get_all(user_id="asha"))',
    '_ = mem.add("I moved to Pune last week for a new job.", user_id="asha")',
    'ctx = mem.search("Am I allergic to anything?", user_id="asha", budget=50)',
    "print(ctx.text)",
    'print(mem.search("Where did I move to?", user_id="asha", budget=50).text)',
]


def seed() -> None:
    if os.path.exists(DB):
        os.remove(DB)
    memory = Memory(DB)
    for day in range(30):
        question, answer = SMALL_TALK[day % len(SMALL_TALK)]
        turns = [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        memory.add(turns, user_id="asha", timestamp=START + timedelta(days=day))
    allergy = [
        {
            "role": "user",
            "content": "I'm allergic to peanuts, so never suggest satay or peanut chutney.",
        },
        {"role": "assistant", "content": "Understood: no peanuts in any suggestion."},
    ]
    memory.add(allergy, user_id="asha", timestamp=START + timedelta(days=12, hours=2))
    memory.store.close()


def type_line(line: str) -> None:
    sys.stdout.write(">>> ")
    sys.stdout.flush()
    time.sleep(0.6)
    for char in line:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.035)
    sys.stdout.write("\n")
    sys.stdout.flush()


def main() -> None:
    seed()
    console = code.InteractiveConsole()
    for line in LINES:
        type_line(line)
        console.push(line)
        sys.stdout.flush()
        time.sleep(1.2)
    sys.stdout.write(">>> ")
    sys.stdout.flush()
    time.sleep(4)
    sys.stdout.write(
        "\x1b[?25h"
    )  # no visible change: it keeps the last frame on screen before the replay
    sys.stdout.flush()


if __name__ == "__main__":
    main()
