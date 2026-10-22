"""What kind of question a memory search answers, read from the question's form alone (fixed patterns, no model).

The kind decides how the budget is spent:

* ``overview``: a summary or recap, how something developed or progressed, or the order in which things happened.
  Answered from the opening of many turns (the digest), so the whole story fits.
* ``lookup``: a plain fact about the past ("What is my current salary?", "When did I say ...?", "How many ... did
  I ...?") or a history check ("Have I ever ...?", "Did I ... before?"). The whole budget goes to relevance: no
  requests section and no preferences section, which would only crowd out the one turn that holds the answer.
* ``advice``: a request for help, a recommendation or a plan ("Can you suggest ...", "How should I ...", "Walk me
  through ..."). The answer should follow the user's standing requests and stated preferences, so both sections
  are shown.
* ``other``: anything else. The standing requests that best match the question are shown; no preferences section.

Every pattern is ordinary English a user would write to any assistant; none is keyed to a dataset's wording.
"""

from __future__ import annotations

import re

OVERVIEW, LOOKUP, ADVICE, OTHER = "overview", "lookup", "advice", "other"

# Summaries, recaps, overviews and the order of events: always an overview.
_SUMMARY = re.compile(
    r"\b(?:summar(?:y|ies|ise|ize|ised|ized|ising|izing)|recap|overview|"
    r"(?:what|everything) (?:have|did) (?:we|i|you) (?:discuss|discussed|cover|covered|talk|talked)|"
    r"key (?:points|takeaways)|main (?:points|topics)|"
    r"order in which|in (?:what|which|the|chronological) order|in order|chronolog\w*|timeline|"
    r"sequence of|what happened (?:first|next|after that|before that))\b",
    re.IGNORECASE,
)
# How something developed or progressed over time: an overview, unless the question asks what was said (below).
_DEVELOPMENT = re.compile(
    r"\b(?:over the course of|over time|throughout (?:our|my|the|these|this|all) \w+)\b"
    r"|\bhow (?:did|has|have|do|does|is|are|was|were) .{0,120}?\b(?:progress(?:ed|ing)?|evolv(?:e|ed|ing)|"
    r"develop(?:ed|ing)?|unfold(?:ed|ing)?|shift(?:ed|ing)?|grow(?:n|ing)?|grew)\b",
    re.IGNORECASE,
)
# A question about what was said, decided or done: "remind me", "did I say", "you told me", "what was my ...".
_RECALL = re.compile(
    r"\b(?:remind me|do you remember|did (?:i|we|you) (?:say|mention|tell|share|note|ask|decide|choose|pick|"
    r"plan|recommend|suggest|advise)|(?:i|you|we) (?:said|mentioned|told|shared|noted|decided)|"
    r"what (?:was|were) (?:the|my|our|your))\b",
    re.IGNORECASE,
)
# "Have I ever ...?", "Did I ... before?", "Have I completed ...?", "Do I usually ...?": a check of the history.
_HISTORY = re.compile(
    r"\b(?:have|has|had|did|do|does|was|were) (?:i|we|you|he|she|they|\w+) (?:ever|already|previously)\b"
    r"|\bever (?:been|had|done|tried|mentioned|said|told|asked|used|attended|visited|worked|met)\b"
    r"|^\s*(?:have|has|had|did|do|does|was|were|am|is|are) (?:i|we|my|our)\b",
    re.IGNORECASE,
)
# A request for help, advice, a recommendation, a plan or an explanation.
_ADVICE = re.compile(
    r"\b(?:suggest(?:ion|ions)?|recommend(?:ation|ations)?|advi[cs]e|tips?|ideas?|options?|strateg(?:y|ies)|"
    r"should (?:i|we)|could (?:i|we)|can (?:i|we)|(?:i|we) (?:should|could|can|might|need to)|"
    r"how (?:do|can|could|should|would|might) (?:i|we|you|one)|"
    r"what (?:would|should|could|can) (?:you|i|we)|what do (?:i|we) need|"
    r"(?:can|could|would|will) you|help me|walk me through|show me|guide me|teach me|"
    r"(?:i'?m|i am) (?:planning|thinking|looking|trying|preparing|hoping|working on|getting ready)|"
    r"good (?:time|way|idea|place|choice)|(?:best|better) (?:way|approach|option|practice)|what's the best|"
    r"what are (?:some|the) (?:ways|steps))\b"
    r"|^\s*(?:please\s+)?(?:give|show|write|create|make|draft|list|suggest|recommend|explain|help|plan|outline|"
    r"describe|tell|compare|design|build|fix|debug|review|prepare)\b",
    re.IGNORECASE,
)
# A plain question about a fact: a question word, a count or amount, a choice between options, or "how did I ...".
_FACT = re.compile(
    r"^\s*(?:and |so |also |by the way,? )?(?:what|which|when|where|who|whom|whose|why|"
    r"(?:on|at|in|by|for|from|until|since) (?:what|which|when))\b"
    r"|\bhow (?:many|much|long|old|far|often|soon|big|large|fast|high|low)\b"
    r"|\bwhich (?:one|of)\b|\bhow (?:did|had) (?:i|we|my|our)\b|\bhow (?:have|has) (?:i|we)\b",
    re.IGNORECASE,
)
_PERSONAL = re.compile(r"\b(?:i|i'm|i've|i'd|my|me|mine|we|our|us)\b", re.IGNORECASE)


# The order in which things came up, or how they progressed: asked about what the user brought up, turn by turn.
_ORDERING = re.compile(
    r"\b(?:order in which|in (?:what|which|the|chronological) order|in order|chronolog\w*|timeline|sequence|"
    r"what happened (?:first|next|after that|before that)|(?:first|then|next|later) (?:i|we) (?:asked|mentioned|"
    r"brought up|talked about))\b"
    r"|\bhow (?:did|has|have|do|does|is|are|was|were) .{0,120}?\b(?:progress(?:ed|ing)?|evolv(?:e|ed|ing)|"
    r"develop(?:ed|ing)?|unfold(?:ed|ing)?|shift(?:ed|ing)?)\b",
    re.IGNORECASE,
)


def ordering(query: str) -> bool:
    """True for an overview question about the order or progression of what was brought up."""
    return bool(_ORDERING.search(" ".join(query.split())))


def route(query: str) -> str:
    """The kind of question (``overview``, ``lookup``, ``advice`` or ``other``); see the module docstring."""
    text = " ".join(query.split())
    if _SUMMARY.search(text):
        return OVERVIEW
    if _RECALL.search(text):
        return LOOKUP
    if _DEVELOPMENT.search(text):
        return OVERVIEW
    if _HISTORY.search(text):
        return LOOKUP
    if _ADVICE.search(text):
        return ADVICE
    if _FACT.search(text) and _PERSONAL.search(text):
        return LOOKUP
    return OTHER


# A first-person statement of what the user likes, prefers, usually does or wants to avoid. Only user turns are
# read, and only the sentence that states it is shown.
PREFERENCE = re.compile(
    r"\bi(?:'d| would) (?:much |really )?(?:rather|prefer)\b"
    r"|\bi (?:really |strongly |generally |usually |always |definitely |much |personally |tend to )?"
    r"(?:prefer|favou?r|prioriti[sz]e|value|lean (?:towards?|toward))\b"
    r"|\bi (?:really |generally |usually |always |definitely )?(?:like|love|enjoy)\b.{0,60}?\b(?:better|more|most|"
    r"over|than|instead)\b"
    r"|\bi (?:usually|typically|normally|generally|tend to|like to|love to|always try to|prefer to)\b"
    r"|\bi always\b.{0,80}?\b(?:when|whenever|before|after)\b"
    r"|\bmy (?:favou?rite|preference|preferred|priority|priorities|go-to)\b"
    r"|\bi (?:don'?t|do not|never|really don'?t) (?:like|enjoy|want|care for|prefer)\b"
    r"|\bi (?:hate|dislike|can'?t stand|avoid)\b"
    r"|\b(?:works?|worked) (?:best|better) for me\b|\bi find (?:it )?(?:\w+ ){0,4}(?:easier|harder|clearer|"
    r"more (?:helpful|useful|effective|comfortable))\b|\bmore comfortable (?:with|using)\b"
    r"|\brather than\b",
    re.IGNORECASE,
)
