"""Indic text in lexical relevance and adaptive planning.

Regression guard for 0.8.0, where the planner's extractive candidates came from query-focused
selection, whose last resort cut a one-sentence Bengali or Odia document at a word boundary (losing a
date or a reference number); the planner kept that fragment and the irrelevant document instead of
the whole relevant one. The examples are written for these tests; none is taken from a benchmark corpus.
"""

from __future__ import annotations

import re
import unicodedata

import pytest

import llmslim.tokenization as tokenization
from llmslim import plan_context
from llmslim.planning.candidates import generate_candidates
from llmslim.planning.models import CandidateMethod
from llmslim.planning.planner import AdaptiveContextPlanner
from llmslim.planning.policy import resolve_policy
from llmslim.planning.scoring import lexical_relevance, lexical_terms
from llmslim.tokenization import split_sentences, words

HINDI = "आदेश 4471 कल गोदाम से भेजा गया। डिलीवरी की तारीख १२ मार्च २०२७ है। आज शहर में मौसम साफ़ रहेगा।"
BENGALI = (
    "রোগীর রিপোর্ট আজ সকালে পাঠানো হয়েছে। "
    "পরবর্তী পরীক্ষা ১৫ জানুয়ারি ২০২৭ তারিখে। "
    "হাসপাতালের ক্যান্টিন সন্ধ্যায় বন্ধ থাকে।"
)
ODIA = "ଆବେଦନ ନମ୍ବର 5521 ଗ୍ରହଣ କରାଯାଇଛି। ଯାଞ୍ଚ ଶେଷ ତାରିଖ ୨୮ ଫେବୃଆରୀ। ଆଜି ବର୍ଷା ହେବାର ସମ୍ଭାବନା ଅଛି।"
TAMIL = "பார்சல் 8812 நேற்று அனுப்பப்பட்டது. டெலிவரி தேதி மார்ச் 3. இன்று மாலை மழை பெய்யும்."
HINGLISH = "Order 7781 kal dispatch hua. Delivery date 5 March hai. Aaj shaam baarish hogi."

ONE_SENTENCE = [
    "চুক্তি KX-12 নবায়ন হয়েছে এবং মেয়াদ শেষ ২৯ ডিসেম্বর ২০২৭।",
    "ଅଭିଯୋଗ CM-40 ବନ୍ଦ ହୋଇଛି ଏବଂ ଟ୍ରାକିଂ ସଂଖ୍ୟା 90431।",
    "ग्राहक GH-5 का खाता 3 अप्रैल 2027 को सक्रिय हुआ।",
    "Customer GH-5 ka account 3 April 2027 ko active hua aur limit 90,000 rupees hai.",
]


@pytest.fixture(params=["nltk-if-available", "regex"])
def splitter(request, monkeypatch):
    """Run sentence tests with the default splitter and with the dependency-free regex fallback."""
    if request.param == "regex":
        monkeypatch.setattr(tokenization, "_try_nltk_split", lambda text: None)
    return request.param


def _items(documents, query):
    planner = AdaptiveContextPlanner()
    items = planner._normalize(
        messages=[], documents=documents, tools=[], memories=[], query=query, policy=planner.policy
    )
    return [item for item in items if item.source != "query"]


# ------------------------------------------------------------------ words


@pytest.mark.parametrize(
    "text, expected",
    [
        ("डिलीवरी की तारीख", ["डिलीवरी", "की", "तारीख"]),
        ("পরবর্তী পরীক্ষা", ["পরবর্তী", "পরীক্ষা"]),
        ("ଯାଞ୍ଚ ଶେଷ ତାରିଖ", ["ଯାଞ୍ଚ", "ଶେଷ", "ତାରିଖ"]),
        ("டெலிவரி தேதி", ["டெலிவரி", "தேதி"]),
    ],
)
def test_indic_words_keep_vowel_signs_and_viramas(text, expected):
    assert words(text) == expected
    # Python's \w alone cuts these words at every combining mark.
    assert re.findall(r"[^\W_]+", text) != expected


def test_native_digits_are_ascii_digits():
    assert words("১৫ জানুয়ারি ২০২৭") == ["15", "জানুয়ারি", "2027"]
    assert words("१२ मार्च २०२७") == ["12", "मार्च", "2027"]
    assert words("୨୮ ଫେବୃଆରୀ") == ["28", "ଫେବୃଆରୀ"]
    assert words("௧௨ ௩") == ["12", "3"]


def test_words_normalise_nukta_and_zero_width_joiners():
    # Devanagari QA typed as one code point (a composition exclusion) or as KA + NUKTA.
    precomposed = "".join(map(chr, (0x0958, 0x093E, 0x0928, 0x0942, 0x0928)))
    decomposed = "".join(map(chr, (0x0915, 0x093C, 0x093E, 0x0928, 0x0942, 0x0928)))
    assert precomposed != decomposed
    assert words(precomposed) == words(decomposed) == [unicodedata.normalize("NFC", decomposed)]
    malayalam = "".join(map(chr, (0x0D28, 0x0D3F, 0x0D32, 0x0D2F, 0x0D4D)))
    zero_width_joiner = chr(0x200D)
    assert words(malayalam + zero_width_joiner) == [malayalam]
    assert words(zero_width_joiner) == []


def test_ascii_words_are_unchanged():
    text = "Order CUST-HI-8 ka payment_status 19 September, amount 72,300."
    assert words(text) == re.findall(r"[^\W_]+", text)


# ------------------------------------------------------------------ planner relevance


@pytest.mark.parametrize(
    "query, relevant, unrelated",
    [
        ("ଯାଞ୍ଚ ତାରିଖ", ODIA, "ଏହି ଅନୁଚ୍ଛେଦ ଖେଳ ଖବର ବିଷୟରେ।"),
        ("পরবর্তী পরীক্ষা", BENGALI, "এই অনুচ্ছেদটি খেলার খবর নিয়ে।"),
        ("डिलीवरी की तारीख", HINDI, "यह अनुच्छेद खेल समाचार के बारे में है।"),
        ("டெலிவரி தேதி", TAMIL, "இந்த பத்தி விளையாட்டு செய்திகளைப் பற்றியது."),
        ("delivery date", HINGLISH, "Ye paragraph cricket scores ke baare mein hai."),
    ],
)
def test_lexical_relevance_separates_relevant_from_unrelated(query, relevant, unrelated):
    assert lexical_terms(query)
    assert lexical_relevance(query, relevant) > 0.3
    assert lexical_relevance(query, unrelated) == 0.0


def test_lexical_relevance_matches_digits_across_scripts():
    assert {"2027", "15"} <= lexical_terms(BENGALI)
    assert lexical_relevance("2027", BENGALI) > 0.5


# ------------------------------------------------------------------ planner candidates


@pytest.mark.parametrize("query", ["স্থিতি", "status of the account", ""])
def test_one_sentence_has_no_extractive_candidate(query):
    """A single sentence is kept raw or dropped; it is never cut at a word boundary."""
    policy = resolve_policy(None)
    for item in _items(ONE_SENTENCE, query):
        candidates = generate_candidates(item, query=query, policy=policy).candidates
        assert {c.method for c in candidates} == {CandidateMethod.RAW, CandidateMethod.DROP}


@pytest.mark.parametrize(
    "text, query",
    [
        (HINDI, "डिलीवरी की तारीख"),
        (BENGALI, "পরবর্তী পরীক্ষা"),
        (ODIA, "ଯାଞ୍ଚ ତାରିଖ"),
        (TAMIL, "டெலிவரி தேதி"),
        (HINGLISH, "delivery date"),
        (
            "The renewal for account 7 is due on 3 April 2027. The audit closed in March. "
            "Billing moved to the new ledger, and the old export was archived.",
            "account renewal date",
        ),
    ],
)
@pytest.mark.parametrize("preset", ["balanced", "cost_first", "quality_first"])
def test_extractive_candidates_are_whole_sentences(splitter, text, query, preset):
    policy = resolve_policy(preset)
    whole = set(split_sentences(text))
    (item,) = _items([text], query)
    extractive = [
        candidate
        for candidate in generate_candidates(item, query=query, policy=policy).candidates
        if candidate.method is CandidateMethod.EXTRACTIVE_COMPRESSED
    ]
    for candidate in extractive:
        assert set(split_sentences(candidate.content)) <= whole


# ------------------------------------------------------------------ planner end to end


@pytest.mark.parametrize(
    "query, relevant, facts, unrelated",
    [
        (
            "ଅଭିଯୋଗ ସ୍ଥିତି",
            ONE_SENTENCE[1],
            ["CM-40", "90431"],
            "ଏହି ଅନୁଚ୍ଛେଦ ଖେଳ ଖବର ବିଷୟରେ ଅସମ୍ବନ୍ଧିତ ସୂଚନା ଦିଏ।",
        ),
        (
            "চুক্তি নবায়ন",
            ONE_SENTENCE[0],
            ["KX-12", "২৯ ডিসেম্বর ২০২৭"],
            "এই অনুচ্ছেদটি আবহাওয়া নিয়ে অপ্রাসঙ্গিক তথ্য দেয়।",
        ),
        (
            "खाता सक्रिय",
            ONE_SENTENCE[2],
            ["GH-5", "3 अप्रैल 2027"],
            "यह अनुच्छेद खेल समाचार के बारे में असंबंधित जानकारी है।",
        ),
        (
            "account active",
            ONE_SENTENCE[3],
            ["GH-5", "3 April 2027", "90,000"],
            "Ye paragraph cricket scores aur traffic ke baare mein hai.",
        ),
    ],
)
def test_planner_keeps_the_relevant_document_whole_under_budget(query, relevant, facts, unrelated):
    roomy = plan_context(
        documents=[unrelated, relevant],
        query=query,
        max_input_tokens=10_000,
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    )
    costs = [decision.selected.token_cost for decision in roomy.decisions]
    plan = plan_context(
        documents=[unrelated, relevant],
        query=query,
        max_input_tokens=sum(costs) - costs[1] // 2,  # both documents no longer fit
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    )
    assert plan.feasible
    by_text = {decision.item.content: decision for decision in plan.decisions}
    assert by_text[relevant].selected.method is CandidateMethod.RAW
    assert by_text[unrelated].selected.method is CandidateMethod.DROP
    assert all(fact in plan.final_context for fact in facts)
    assert by_text[relevant].selected.provenance["score"]["relevance"] > 0.3
    assert by_text[unrelated].selected.provenance["score"]["relevance"] == 0.0
