#!/usr/bin/env python3
"""Example: Query-aware compression for RAG (Retrieval-Augmented Generation) pipelines.

In a typical RAG setup you retrieve N document chunks from a vector DB
and stuff them into the prompt as context.  Most of that context is only
tangentially relevant.  llmslim lets you aggressively compress
the retrieved chunks while keeping the parts most useful for answering
the user's specific question.

Usage:
    pip install "llmslim[all]"
    python examples/rag_pipeline_example.py
"""

from llmslim import compress_documents, estimate_cost_savings


def main():
    # Simulated retrieved chunks from a vector database
    # (in production these come from Pinecone, Weaviate, Chroma, etc.)
    retrieved_chunks = [
        (
            "FastAPI is a modern, high-performance web framework for building "
            "APIs with Python 3.7+ based on standard Python type hints. It is "
            "built on top of Starlette for the web parts and Pydantic for the "
            "data parts. FastAPI is one of the fastest Python frameworks "
            "available, rivaling NodeJS and Go in performance benchmarks. "
            "The framework was created by Sebastián Ramírez and first released "
            "in 2018. It supports async/await natively, making it ideal for "
            "high-concurrency applications. FastAPI automatically generates "
            "OpenAPI documentation for your API endpoints. The interactive "
            "docs are available at /docs (Swagger UI) and /redoc (ReDoc). "
            "FastAPI uses dependency injection extensively, which makes "
            "testing and code reuse straightforward."
        ),
        (
            "Authentication in FastAPI can be implemented using several "
            "approaches. The most common is OAuth2 with JWT (JSON Web Tokens). "
            "FastAPI provides built-in security utilities in the "
            "fastapi.security module. You must use HTTPS in production to "
            "protect tokens in transit. The OAuth2PasswordBearer class creates "
            "a dependency that extracts the token from the Authorization "
            "header. JWT tokens should be signed with a strong secret key "
            "using the HS256 algorithm. Never store passwords in plain text; "
            "always use bcrypt or argon2 for hashing. Token expiration should "
            "be set to a short duration (15-30 minutes) for access tokens. "
            "Refresh tokens can have a longer lifetime (7-30 days). "
            "Implement token revocation by maintaining a blacklist in Redis "
            "or your database. Always validate the token signature and "
            "expiration on every request."
        ),
        (
            "Middleware in FastAPI allows you to process requests and responses "
            "globally. You can add CORS middleware using CORSMiddleware from "
            "starlette.middleware.cors. Custom middleware can be created by "
            "defining an async function that takes the request and a "
            "call_next callable. Middleware is useful for logging, request "
            "timing, authentication checks, and rate limiting. The order "
            "of middleware matters — they are executed in the order they are "
            "added. GZip middleware can compress responses to reduce bandwidth. "
            "Trusted host middleware validates the Host header to prevent "
            "host header injection attacks. You can also use middleware to "
            "add custom headers to all responses."
        ),
        (
            "Database integration with FastAPI typically uses SQLAlchemy or "
            "Tortoise ORM. For SQLAlchemy, you create a session dependency "
            "that yields a database session and ensures it is closed after "
            "the request. Alembic is the standard migration tool for "
            "SQLAlchemy. You must never commit transactions in your route "
            "handlers directly; use the dependency injection pattern instead. "
            "Connection pooling is handled by SQLAlchemy's engine. For async "
            "database access, use databases library or SQLAlchemy 2.0's "
            "async engine. Always use parameterized queries to prevent SQL "
            "injection attacks. Database models should be defined separately "
            "from Pydantic schemas to maintain a clean separation of concerns."
        ),
        (
            "Testing FastAPI applications is straightforward using the "
            "TestClient from Starlette. The TestClient wraps httpx and "
            "provides a requests-like interface. You can override dependencies "
            "using app.dependency_overrides to mock database sessions, "
            "authentication, and external services. Pytest fixtures work "
            "well for setting up and tearing down test databases. Integration "
            "tests should use a separate test database. Always test both "
            "happy paths and error cases. Use factory patterns to create "
            "test data consistently. Code coverage should be above 80% for "
            "production applications."
        ),
    ]

    user_query = "How do I implement JWT authentication in FastAPI?"

    print("=" * 60)
    print("RAG PIPELINE COMPRESSION EXAMPLE")
    print("=" * 60)
    print(f"\nUser query: {user_query!r}")
    print(f"Retrieved chunks: {len(retrieved_chunks)}")

    # --- Compress with query awareness ---
    results = compress_documents(
        retrieved_chunks,
        query=user_query,  # Favor sentences relevant to authentication
        target_ratio=0.4,  # Aggressive 60% reduction
    )

    # --- Show per-chunk results ---
    print("\n--- Per-Chunk Compression ---")
    total_orig = 0
    total_comp = 0
    for i, result in enumerate(results):
        total_orig += result.original_tokens
        total_comp += result.compressed_tokens
        print(
            f"  Chunk {i + 1}: {result.original_tokens:>4} -> "
            f"{result.compressed_tokens:>4} tokens "
            f"({result.reduction_percent}% reduction)"
        )

    total_saved = total_orig - total_comp
    total_reduction = round((total_saved / total_orig) * 100, 1)

    print(f"\n  Total: {total_orig} -> {total_comp} tokens ({total_reduction}% reduction)")
    print(f"  Tokens saved: {total_saved}")

    # --- Build the compressed context ---
    compressed_context = "\n\n---\n\n".join(r.compressed_text for r in results)
    print("\n--- Compressed Context (ready for LLM) ---")
    print(
        compressed_context[:500] + "...\n" if len(compressed_context) > 500 else compressed_context
    )

    # --- Cost savings ---
    print("--- Annual Cost Savings ---")
    for model in ["gpt-5", "claude-opus-4.8", "gemini-2.5-pro"]:
        est = estimate_cost_savings(
            total_orig,
            total_comp,
            model=model,
            requests_per_day=50_000,
        )
        print(f"  {model}: ${est.annual_savings_usd:,.2f}/year at 50K req/day")

    print("\n[OK] Query-aware compression keeps auth-related content, removes noise!")


if __name__ == "__main__":
    main()
