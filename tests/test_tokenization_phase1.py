"""Phase 1 (v0.3.1) tokenization tests: inline code spans + CJK boundaries.

Covers P0-2 (inline backtick code-span protection) and P1-2 (CJK
ideographic sentence boundaries).  See
``docs/phase-1/IMPLEMENTATION_PLAN.md`` §5.3, §6, §7.
"""

from __future__ import annotations

from llmslim.tokenization import split_sentences

# ---------------------------------------------------------------------------
# Inline code span protection (P0-2)
# ---------------------------------------------------------------------------


class TestInlineCodeSpans:
    def test_period_inside_inline_span_not_split(self):
        """A period inside `config.v1.json` must not split the sentence."""
        text = "Edit the `config.v1.json` file then restart the service."
        sentences = split_sentences(text)
        assert len(sentences) == 1
        assert "`config.v1.json`" in sentences[0]

    def test_dotted_call_inside_span(self):
        text = "Call `foo.bar().baz()` before you continue with setup."
        sentences = split_sentences(text)
        assert len(sentences) == 1
        assert "`foo.bar().baz()`" in sentences[0]

    def test_multiple_inline_spans_single_sentence(self):
        text = "Use `a.b` and `c.d` and `e.f` together in one call."
        sentences = split_sentences(text)
        assert len(sentences) == 1
        assert sentences[0].count("`") == 6

    def test_punctuation_inside_span_preserved(self):
        text = "Run `x = 1; y = 2! z = 3?` and observe the output."
        sentences = split_sentences(text)
        assert len(sentences) == 1
        assert "`x = 1; y = 2! z = 3?`" in sentences[0]

    def test_inline_span_with_following_sentence(self):
        text = "Set `a.b.c` now. Then verify the result carefully."
        sentences = split_sentences(text)
        assert len(sentences) == 2
        assert "`a.b.c`" in sentences[0]

    def test_fenced_block_still_protected(self):
        text = "Here is code:\n```python\nx = 1\nprint(x)\n```\nThat is all."
        sentences = split_sentences(text)
        assert any("```" in s and "print(x)" in s for s in sentences)

    def test_malformed_backtick_does_not_crash(self):
        # Unbalanced backtick — must not raise, must return something.
        text = "This has an unbalanced ` backtick and keeps going normally."
        sentences = split_sentences(text)
        assert len(sentences) >= 1

    def test_normal_prose_unaffected(self):
        text = "First sentence here. Second sentence here. Third one too."
        sentences = split_sentences(text)
        assert len(sentences) == 3


# ---------------------------------------------------------------------------
# CJK sentence boundaries (P1-2)
# ---------------------------------------------------------------------------


class TestCJKBoundaries:
    def test_chinese_full_stop_splits(self):
        text = "欢迎使用压缩工具。这是第二句话。这是第三句话。"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_japanese_full_stop_splits(self):
        text = "これはテストです。二番目の文です。三番目の文です。"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_cjk_exclamation_and_question(self):
        text = "太好了！你确定吗？我们开始吧。"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_no_space_cjk_splits(self):
        """CJK sentences without any whitespace still split."""
        text = "第一。第二。第三。"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_mixed_english_chinese(self):
        text = "This is English. 这是中文。Back to English again."
        sentences = split_sentences(text)
        # 3 logical sentences: EN, ZH, EN.
        assert len(sentences) == 3

    def test_mixed_english_japanese(self):
        text = "Start here. 日本語の文です。End here."
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_western_punctuation_still_works(self):
        text = "Hello world. How are you? I am fine!"
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_cjk_punct_adjacent_to_bracket(self):
        text = "他说（很重要）。我们记住了。"
        sentences = split_sentences(text)
        assert len(sentences) == 2
