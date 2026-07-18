"""Example demonstrating llmslim v0.3.0 semantic rewriting and hybrid strategies."""

from llmslim import CallableProvider, RewriteRequest, compress

SAMPLE_PROMPT = (
    "You are an AI assistant helping a research engineer. "
    "Rule 1: Always validate user inputs carefully. "
    "Rule 2: Never expose credentials, API keys, or secret tokens. "
    "Rule 3: Ensure output is structured as JSON. "
    "Kubernetes HPA scales pods based on CPU utilization metrics. "
    "The API endpoint is https://api.example.com/v1/status."
)


def mock_llm_provider(request: RewriteRequest) -> str:
    """Simulates an LLM rewriting the prompt."""
    print(f"\n--- [LLM Provider Invoked with Template '{request.template_name}'] ---")
    print(f"System Prompt:\n{request.system_prompt}")
    print(f"User Prompt:\n{request.user_prompt}\n")

    return (
        "You are an AI assistant helping a research engineer. "
        "Rule 1: Always validate user inputs carefully. "
        "Rule 2: Never expose credentials, API keys, or secret tokens. "
        "Rule 3: Ensure output is structured as JSON. "
        "Kubernetes HPA scales pods based on CPU metrics. "
        "API endpoint: https://api.example.com/v1/status."
    )


def main():
    provider = CallableProvider(mock_llm_provider, name="custom_mock_llm")

    # 1. Extractive strategy (default)
    res_ext = compress(SAMPLE_PROMPT, target_ratio=0.5, strategy="extractive")
    print("=== Extractive Result ===")
    print(res_ext.compressed_text)

    # 2. Rewrite strategy
    res_rew = compress(
        SAMPLE_PROMPT,
        target_ratio=0.5,
        strategy="rewrite",
        provider=provider,
    )
    print("=== Rewrite Result ===")
    print(res_rew.compressed_text)
    print("\n--- Detailed Summary ---")
    print(res_rew.detailed_summary())

    # 3. Hybrid strategy (Extractive -> Rewrite)
    res_hyb = compress(
        SAMPLE_PROMPT,
        target_ratio=0.5,
        strategy="hybrid",
        provider=provider,
    )
    print("\n=== Hybrid Result ===")
    print(res_hyb.compressed_text)
    print("\n--- Detailed Summary ---")
    print(res_hyb.detailed_summary())


if __name__ == "__main__":
    main()
