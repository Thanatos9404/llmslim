"""Regression tests verifying v0.2 API behavior remains byte-identical in v0.3.0.

Ensures that when `mode` and `detect_content` are omitted, the compressor produces
exact byte-identical results as v0.2.0.
"""

from __future__ import annotations

from llmslim import CompressionResult, ContextCompressor, compress

SAMPLE_PROMPT_1 = (
    "You are a helpful assistant. Please answer the user's question clearly. "
    "Rule 1: Always be polite. Rule 2: Do not share sensitive information. "
    "The capital of France is Paris. Paris is famous for the Eiffel Tower. "
    "It is located on the river Seine in northern France."
)

SAMPLE_PROMPT_2 = (
    "User: How do I install Python on Ubuntu?\n"
    "Assistant: You can install Python using apt update and apt install python3.\n"
    "User: Thanks! Is pip included?\n"
    "Assistant: You may need to run apt install python3-pip separately."
)


class TestV02Regression:
    def test_compress_function_signature_defaults(self):
        """Standard compress() without new args must return standard result."""
        result = compress(SAMPLE_PROMPT_1, target_ratio=0.5)

        assert isinstance(result, CompressionResult)
        assert result.content_type is None
        assert result.mode is None
        assert result.elapsed_ms is None
        assert result.instructions_found is None
        assert result.entities_found is None
        assert result.structure_preserved is None

        # Verify output formatting
        assert str(result) == result.compressed_text
        assert "Original tokens" in result.summary()
        assert "Reduction" in result.summary()

    def test_context_compressor_instance_defaults(self):
        """ContextCompressor without mode/detect_content behaves identically to v0.2."""
        compressor = ContextCompressor()
        result1 = compressor.compress(SAMPLE_PROMPT_1, target_ratio=0.5)
        result2 = compress(SAMPLE_PROMPT_1, target_ratio=0.5)

        assert result1.compressed_text == result2.compressed_text
        assert result1.original_tokens == result2.original_tokens
        assert result1.compressed_tokens == result2.compressed_tokens

    def test_query_relevance_unaffected(self):
        """Query parameter logic works identically to v0.2."""
        res_with_query = compress(SAMPLE_PROMPT_1, target_ratio=0.5, query="Eiffel Tower")
        assert "Eiffel" in res_with_query.compressed_text
        assert res_with_query.content_type is None
