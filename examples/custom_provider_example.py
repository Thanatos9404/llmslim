"""Example demonstrating custom provider implementation by subclassing BaseRewriteProvider."""

from llmslim import BaseRewriteProvider, RewriteRequest, compress


class OpenAIStyleProvider(BaseRewriteProvider):
    """An example provider wrapping OpenAI or compatible HTTP APIs."""

    name = "openai_compatible"

    def __init__(self, api_key: str = "demo_key", model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def rewrite(self, request: RewriteRequest) -> str:
        # In actual production code:
        # response = openai_client.chat.completions.create(
        #     model=self.model,
        #     messages=[
        #         {"role": "system", "content": request.system_prompt},
        #         {"role": "user", "content": request.user_prompt},
        #     ],
        # )
        # return response.choices[0].message.content

        # Simulated response preserving instructions & entities for demonstration
        return (
            "You are an expert system. You must respond in JSON. "
            "Never share sensitive tokens or API keys. "
            "Always validate inputs before processing. "
            "Postgres connection string: postgresql://admin@localhost:5432/db"
        )


def main():
    provider = OpenAIStyleProvider(api_key="sk-demo-12345", model="gpt-4o")

    text = (
        "You are an expert system. You must respond in JSON format. "
        "Rule 1: Never share sensitive tokens, passwords, or API keys. "
        "Rule 2: Always validate inputs before processing downstream requests. "
        "The database endpoint is postgresql://admin@localhost:5432/db. "
        "Ensure all error responses return HTTP status codes."
    )

    result = compress(
        text,
        target_ratio=0.5,
        strategy="rewrite",
        provider=provider,
        required_keywords=["JSON", "postgresql"],
    )

    print("=== Custom Provider Rewrite Result ===")
    print(result.compressed_text)
    print("\n--- Detailed Summary ---")
    print(result.detailed_summary())


if __name__ == "__main__":
    main()
