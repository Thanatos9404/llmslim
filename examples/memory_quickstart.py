"""Agent memory with no LLM in the loop: store turns verbatim, select what the question needs at read time.

Runs offline, with no API key: it fills a SQLite memory with a few weeks of chat, then asks it questions.

    python examples/memory_quickstart.py
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from llmslim.memory import Memory

START = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)

SMALL_TALK = [
    (
        "Can you suggest something quick for dinner?",
        "Try a vegetable khichdi: rice, lentils, cumin and ghee.",
    ),
    (
        "How do I stop my plants from wilting in this heat?",
        "Water early in the morning and move them out of direct sun.",
    ),
    (
        "Any podcast for my commute?",
        "If you like history, try a long-form series on the Mughal empire.",
    ),
]


def main() -> None:
    with TemporaryDirectory() as folder:
        memory = Memory(Path(folder) / "memory.db")
        for day in range(30):
            question, answer = SMALL_TALK[day % len(SMALL_TALK)]
            memory.add(
                [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
                user_id="asha",
                timestamp=START + timedelta(days=day),
            )
        memory.add(
            [
                {
                    "role": "user",
                    "content": "I'm allergic to peanuts, so please never suggest satay or peanut chutney.",
                },
                {"role": "assistant", "content": "Understood: no peanuts in any suggestion."},
            ],
            user_id="asha",
            timestamp=START + timedelta(days=12, hours=2),
        )

        for question in ("Am I allergic to anything?", "What did you suggest for dinner?"):
            context = memory.search(question, user_id="asha", budget=120)
            print(f"Q: {question}")
            print(
                f"   {context.history_tokens:,} tokens of history -> {context.tokens} tokens of context"
            )
            print("   " + context.text.replace("\n", "\n   "))
            print()
        memory.store.close()


if __name__ == "__main__":
    main()
