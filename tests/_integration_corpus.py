"""Toy corpus shared by the LangChain, LlamaIndex and Haystack adapter tests."""

from __future__ import annotations

from llmslim import count_tokens

QUERY = "How many days do I have to return an item for a refund?"
TARGET_RATIO = 0.25
ANSWER = "30 days"

# (id, source, text). The empty and whitespace-only documents must be dropped.
CORPUS = [
    (
        "shipping",
        "shipping.md",
        "Standard shipping takes three to seven business days within the country. "
        "Express shipping arrives in one or two business days and costs fifteen dollars. "
        "We ship to forty countries, and international orders clear customs in about a week. "
        "Tracking numbers are emailed as soon as the parcel leaves the warehouse.",
    ),
    ("blank", "blank.md", ""),
    (
        "refunds",
        "refunds.md",
        "You can return any item within 30 days of delivery for a full refund. "
        "Refunds go back to the original payment method within five business days. "
        "Items must be unused and in their original packaging. "
        "Gift cards and final-sale items cannot be returned.",
    ),
    (
        "about",
        "about.md",
        "The company was founded in 2015 by two engineers in Pune. "
        "Our team of eighty people works across design, engineering and support. "
        "The office has a rooftop garden and a small library of design books. "
        "Every Friday afternoon the team hosts an open demo for customers.",
    ),
    ("spaces", "spaces.md", "   \n  "),
]

TEXTS = [text for _, _, text in CORPUS]
NON_EMPTY = [doc_id for doc_id, _, text in CORPUS if text.strip()]
# The shared budget compress_documents uses for the non-empty documents.
BUDGET = round(sum(count_tokens(t) for t in TEXTS if t.strip()) * TARGET_RATIO)


class PreferringScorer:
    """A custom relevance scorer that records its calls and prefers texts containing ``word``."""

    def __init__(self, word: str) -> None:
        self.word = word
        self.calls: list = []

    def __call__(self, query, texts):
        self.calls.append(len(texts))
        return [1.0 if self.word in text.lower() else 0.0 for text in texts]
