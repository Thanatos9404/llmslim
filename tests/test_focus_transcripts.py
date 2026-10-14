"""Speaker-prefixed transcripts ("[8 May 2023] Caroline: ...") are selected turn by turn."""

from llmslim import compress_documents
from llmslim.focus import render, segment, select

FILLER = [
    "Melanie: The weather was lovely at the lake this weekend, we stayed out until sunset.",
    "Caroline: That sounds relaxing. I spent most of Saturday cleaning out the garage.",
    "Melanie: The kids found a box of old board games and wanted to play all of them.",
    "Caroline: Ha, we did that too once. Monopoly took four hours and nobody finished.",
    "Melanie: We tried a new pasta recipe for dinner with lemon and roasted garlic.",
    "Caroline: Yum. I have been meaning to cook more instead of ordering takeaway.",
]


def _session(date: str, lines) -> str:
    return "\n".join(f"[{date}] {line}" for line in lines)


def test_transcript_lines_become_turn_units_under_their_shared_stamp():
    text = _session("8 May 2023", FILLER[:4])
    units = segment(text, max_unit_tokens=40)
    assert [u.text for u in units] == FILLER[:4]
    assert all(u.header == "[8 May 2023]" for u in units)


def test_a_question_is_kept_with_the_reply_that_follows_it():
    lines = [
        "Melanie: How long have you been painting?",
        "Caroline: Since I was 17 or so.",
        *FILLER[:2],
    ]
    units = segment(_session("8 May 2023", lines), max_unit_tokens=40)
    assert (
        units[0].text
        == "Melanie: How long have you been painting?\nCaroline: Since I was 17 or so."
    )
    assert len(units) == 3


def test_mixed_stamps_stay_on_their_lines():
    text = (
        "[10:01] Alice: the deploy failed\n[10:02] Bob: which step?\n[10:03] Alice: the migration"
    )
    units = segment(text, max_unit_tokens=40)
    assert [u.text for u in units] == [
        "[10:01] Alice: the deploy failed",
        "[10:02] Bob: which step?\n[10:03] Alice: the migration",
    ]
    assert all(u.header == "" for u in units)


def test_prose_with_a_colon_is_not_a_transcript():
    text = "Note: the museum opens at nine.\nTickets are sold at the door and online.\nParking is free on Sundays."
    units = segment(text, max_unit_tokens=200)
    assert len(units) == 1
    assert units[0].text.startswith("Note: the museum opens at nine. Tickets")


def test_one_speaker_is_not_a_transcript():
    text = "Name: Ada Lovelace\nName: Charles Babbage\nName: Mary Somerville"
    assert len(segment(text, max_unit_tokens=200)) == 1


def test_rendered_turns_keep_their_lines_and_show_the_date_once():
    text = _session("8 May 2023", FILLER[:4])
    units = segment(text, max_unit_tokens=40)
    out = render(units, {u.index: u.text for u in units[:2]})
    assert out == "[8 May 2023]\n" + FILLER[0] + "\n" + FILLER[1]


def test_compress_documents_keeps_the_answer_to_a_question_it_matched():
    """The reply holds the answer but none of the question's words; it comes with the question that does."""
    sessions = [
        _session("8 May 2023", FILLER),
        _session(
            "25 May 2023",
            [
                *FILLER[:3],
                "Caroline: How long have you been creating art?",
                "Melanie: Since I was 17 or so.",
            ],
        ),
        _session("9 June 2023", FILLER[::-1]),
    ]
    out = "\n\n".join(
        r.compressed_text
        for r in compress_documents(
            sessions, query="How long has Melanie been creating art?", target_ratio=0.15
        )
    )
    assert "Since I was 17" in out
    assert "[25 May 2023]" in out


def test_select_counts_the_shared_stamp_once():
    units = segment(_session("8 May 2023", FILLER), max_unit_tokens=40)
    kept = select(units, [1.0] * len(units), budget=10_000, query="lake")
    assert render(units, kept).count("[8 May 2023]") == 1
