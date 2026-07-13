#!/usr/bin/env python3
"""Example: Compressing chat conversation histories before sending to an LLM.

llmslim can shrink long chat histories so you stay within
context windows and cut API costs — without losing the meaning of
earlier turns.

Usage:
    pip install "llmslim[all]"
    python examples/chat_prompt_example.py
"""

from llmslim import compress_chat_messages, count_tokens, estimate_cost_savings


def main():
    # Simulate a multi-turn conversation that has grown long
    conversation = [
        {
            "role": "system",
            "content": (
                "You are an expert Python developer and code reviewer. "
                "You must always suggest best practices. Never suggest "
                "deprecated APIs. Ensure all code examples include error "
                "handling."
            ),
        },
        {
            "role": "user",
            "content": (
                "I'm building a REST API with FastAPI and I need help "
                "designing the authentication system. The application will "
                "serve both web and mobile clients. We need to support "
                "OAuth2 with JWT tokens for stateless authentication. "
                "The system should handle token refresh seamlessly without "
                "requiring users to log in again. We also need role-based "
                "access control with at least three roles: admin, editor, "
                "and viewer. Each role should have different permissions "
                "for CRUD operations. The admin can do everything, the "
                "editor can create and update but not delete, and the "
                "viewer can only read. We're using PostgreSQL for the "
                "database and SQLAlchemy as the ORM. The passwords must "
                "be hashed with bcrypt. Please provide a complete "
                "implementation plan with code examples for each component."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Great question! Here's a comprehensive plan for your "
                "FastAPI authentication system. First, let's set up the "
                "project structure. You'll need several packages: fastapi, "
                "python-jose for JWT handling, passlib with bcrypt for "
                "password hashing, and sqlalchemy for database operations. "
                "The authentication flow works as follows: the user sends "
                "credentials to a login endpoint, the server validates them "
                "against the database, and if valid, returns an access token "
                "and a refresh token. The access token is short-lived, "
                "typically 15-30 minutes, while the refresh token lasts "
                "longer, usually 7 days. For role-based access control, "
                "you'll create a dependency that checks the user's role "
                "against the required role for each endpoint. Here's the "
                "User model with SQLAlchemy: you'll need fields for id, "
                "email, hashed_password, role, is_active, and timestamps. "
                "The password hashing utility should use passlib's "
                "CryptContext with bcrypt scheme. For the JWT utilities, "
                "use python-jose to create and decode tokens with a secret "
                "key and algorithm. The login endpoint should accept "
                "OAuth2PasswordRequestForm and return TokenResponse. "
                "Always validate the token on every protected request "
                "using a Depends() injection. Remember to store the "
                "refresh tokens securely and invalidate them on logout."
            ),
        },
        {
            "role": "user",
            "content": (
                "That's really helpful, thank you! Now I have a follow-up "
                "question about the refresh token mechanism. How should I "
                "handle the case where a refresh token has been compromised? "
                "Should I implement token rotation? Also, what about "
                "concurrent requests — if two requests try to refresh the "
                "same token simultaneously, one of them will fail with the "
                "rotated token approach. How do production systems handle "
                "this race condition? Additionally, should I store refresh "
                "tokens in the database or use a Redis cache for better "
                "performance? What are the trade-offs?"
            ),
        },
    ]

    # --- Show original stats ---
    total_original = sum(count_tokens(m["content"]) for m in conversation)
    print("=" * 60)
    print("CHAT PROMPT COMPRESSION EXAMPLE")
    print("=" * 60)
    print(f"\nOriginal conversation: {len(conversation)} messages, {total_original} tokens")
    print()

    # --- Compress the conversation ---
    compressed = compress_chat_messages(
        conversation,
        target_ratio=0.5,            # Keep ~50% of tokens
        compressible_roles=("user", "assistant"),  # Don't touch system prompt
    )

    # --- Show results ---
    total_compressed = sum(count_tokens(m["content"]) for m in compressed)
    saved = total_original - total_compressed
    reduction = round((saved / total_original) * 100, 1)

    for _i, (orig, comp) in enumerate(zip(conversation, compressed)):
        role = orig["role"]
        orig_tokens = count_tokens(orig["content"])
        comp_tokens = count_tokens(comp["content"])
        status = "PRESERVED" if orig["content"] == comp["content"] else "COMPRESSED"
        print(f"  [{role:>9}] {orig_tokens:>4} -> {comp_tokens:>4} tokens  ({status})")

    print(f"\n  Total: {total_original} -> {total_compressed} tokens ({reduction}% reduction)")
    print(f"  Tokens saved: {saved}")

    # --- Cost savings ---
    print("\n--- Cost Savings at Scale ---")
    for model in ["gpt-5", "claude-sonnet-4.6", "gemini-2.5-pro"]:
        est = estimate_cost_savings(
            total_original, total_compressed,
            model=model,
            requests_per_day=10_000,
        )
        print(f"  {model}: ${est.annual_savings_usd:,.2f}/year at 10K req/day")

    # --- Show that system prompt is untouched ---
    print("\n--- System Prompt (preserved as-is) ---")
    print(f"  {compressed[0]['content'][:80]}...")

    print("\n[OK] Compressed conversation is ready to send to any LLM API!")


if __name__ == "__main__":
    main()
