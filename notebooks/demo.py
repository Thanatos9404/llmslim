#!/usr/bin/env python3
"""Interactive demo script for context-compressor.

This script walks through all major features of the library.
Run it directly or convert it to a Jupyter notebook with jupytext:

    jupytext --to notebook notebooks/demo.py

Usage:
    pip install "context-compressor[all]"
    python notebooks/demo.py
"""

# %% [markdown]
# # 🚀 context-compressor Demo
#
# **Cut your LLM costs by 50% in one line of code.**
#
# This demo walks through the main features of `context-compressor`:
# 1. Basic compression
# 2. Inspecting compression results
# 3. RAG-style query-aware compression
# 4. Chat history compression
# 5. Cost savings estimation
# 6. Advanced configuration

# %% [markdown]
# ## 1. Basic Compression

# %%
from context_compressor import compress

# A sample long prompt
prompt = """
You are a senior software architect helping design a microservices system.
The system processes financial transactions for a fintech startup.
You must ensure all designs comply with PCI DSS requirements.
Never suggest storing raw credit card numbers in application databases.
Always recommend encryption at rest and in transit.

The current architecture uses a monolithic Django application deployed
on a single AWS EC2 instance. The database is PostgreSQL 14 running on
RDS. The application handles approximately 10,000 transactions per day
with peak loads of 500 transactions per minute during business hours.
The team wants to migrate to a microservices architecture to improve
scalability, deployment independence, and team autonomy.

Key requirements include:
1. Transaction processing must complete within 2 seconds end-to-end
2. The system must support at least 5,000 concurrent users
3. Data consistency is critical — no lost or duplicate transactions
4. The system must maintain an audit trail for all financial operations
5. Horizontal scaling should be possible without downtime
6. The migration should be gradual, not a big-bang rewrite

Consider using an event-driven architecture with Apache Kafka for
inter-service communication. Evaluate whether CQRS (Command Query
Responsibility Segregation) would benefit the transaction processing
pipeline. Discuss trade-offs of synchronous vs asynchronous communication
patterns. Recommend a service mesh solution for observability and
traffic management. Address data ownership and the database-per-service
pattern. Suggest a migration strategy that minimizes risk.
"""

result = compress(prompt, target_ratio=0.5)

print("=== Compression Result ===")
print(result.summary())
print()
print("=== Compressed Text ===")
print(result.compressed_text)

# %% [markdown]
# ## 2. Inspecting Results in Detail

# %%
print(f"Original tokens:   {result.original_tokens}")
print(f"Compressed tokens: {result.compressed_tokens}")
print(f"Tokens saved:      {result.tokens_saved}")
print(f"Reduction:         {result.reduction_percent}%")
print(f"Actual ratio:      {result.actual_ratio:.3f}")
print(f"Sentences kept:    {result.sentences_kept}/{result.sentences_total}")
print(f"Chunks:            {result.num_chunks}")
print(f"Backend:           {result.backend}")

# Per-chunk details
if result.chunk_results:
    print("\n=== Per-Chunk Breakdown ===")
    for i, cr in enumerate(result.chunk_results):
        print(f"  Chunk {i}: {cr.original_tokens}->{cr.compressed_tokens} tokens, "
              f"{cr.sentences_kept}/{cr.sentences_total} sentences")

# %% [markdown]
# ## 3. RAG-Style Query-Aware Compression

# %%
documents = [
    "Python is a versatile programming language used in web development, "
    "data science, machine learning, and automation. It was created by "
    "Guido van Rossum and first released in 1991. Python emphasizes code "
    "readability with significant use of whitespace. The language supports "
    "multiple programming paradigms including procedural, object-oriented, "
    "and functional programming. Python's package manager pip provides "
    "access to over 400,000 packages on PyPI.",

    "FastAPI is a modern Python web framework for building APIs. It uses "
    "Python type hints for automatic validation and documentation. FastAPI "
    "is built on Starlette and Pydantic. It supports async/await for "
    "high-performance concurrent request handling. Authentication can be "
    "implemented using OAuth2 with JWT tokens. The framework automatically "
    "generates OpenAPI documentation at the /docs endpoint.",
]

from context_compressor import compress_documents

# Without query — general compression
results_general = compress_documents(documents, target_ratio=0.5)

# With query — favors authentication-related content
results_query = compress_documents(
    documents,
    query="How to implement authentication?",
    target_ratio=0.5,
)

print("=== General Compression ===")
for i, r in enumerate(results_general):
    print(f"  Doc {i}: {r.reduction_percent}% reduction")
    print(f"    -> {r.compressed_text[:100]}...")

print("\n=== Query-Aware Compression ===")
for i, r in enumerate(results_query):
    print(f"  Doc {i}: {r.reduction_percent}% reduction")
    print(f"    -> {r.compressed_text[:100]}...")

# %% [markdown]
# ## 4. Chat History Compression

# %%
from context_compressor import compress_chat_messages

messages = [
    {"role": "system", "content": "You are a helpful coding assistant. You must provide working code."},
    {"role": "user", "content": prompt},  # Reuse the long prompt from above
    {"role": "assistant", "content": (
        "Great question! Let me outline a comprehensive migration strategy. "
        "First, identify bounded contexts in your monolith — transaction "
        "processing, user management, reporting, and notifications are "
        "natural candidates for separate services. Start with the strangler "
        "fig pattern: build new features as microservices while gradually "
        "extracting functionality from the monolith. Use Apache Kafka as "
        "the event backbone for asynchronous communication between services. "
        "Each service should own its data store (database-per-service pattern). "
        "Implement the Saga pattern for distributed transactions. Deploy "
        "Istio as your service mesh for traffic management and observability."
    )},
]

compressed_msgs = compress_chat_messages(messages, target_ratio=0.5)

print("=== Chat Compression ===")
from context_compressor import count_tokens
for orig, comp in zip(messages, compressed_msgs):
    orig_tokens = count_tokens(orig["content"])
    comp_tokens = count_tokens(comp["content"])
    changed = "COMPRESSED" if orig["content"] != comp["content"] else "PRESERVED"
    print(f"  [{orig['role']:>9}] {orig_tokens:>4} -> {comp_tokens:>4} tokens  ({changed})")

# %% [markdown]
# ## 5. Cost Savings Estimation

# %%
from context_compressor import estimate_cost_savings, list_supported_models

print(f"Supported models: {', '.join(list_supported_models())}\n")

result = compress(prompt, target_ratio=0.5)

for model in ["gpt-5", "claude-sonnet-4.6", "gemini-2.5-pro"]:
    est = estimate_cost_savings(
        result.original_tokens,
        result.compressed_tokens,
        model=model,
        requests_per_day=10_000,
    )
    print(f"--- {model} ---")
    print(est.summary())
    print()

# %% [markdown]
# ## 6. Advanced Configuration

# %%
from context_compressor import ContextCompressor

# Custom compressor with tuned parameters
compressor = ContextCompressor(
    max_chunk_tokens=200,          # larger semantic chunks
    similarity_threshold=0.3,      # less sensitive topic splitting
    weights={
        "centrality": 0.4,         # emphasize representativeness
        "instruction": 0.3,        # strong instruction preservation
        "entity": 0.2,             # moderate entity boost
        "position": 0.1,           # less position bias
    },
    preserve_patterns=[
        r"PCI DSS",                # always keep compliance mentions
        r"\$\d+",                  # keep dollar amounts
    ],
)

result = compressor.compress(prompt, target_ratio=0.4)
print("=== Custom Configuration (40% retention) ===")
print(result.summary())
print()
print("Compressed text:")
print(result.compressed_text)

# Check that PCI DSS was preserved
if "PCI DSS" in result.compressed_text:
    print("\n[OK] PCI DSS mention preserved (custom preserve_patterns working!)")

# %% [markdown]
# ## 🎉 That's it!
#
# You've seen how to:
# - Compress any text with a single function call
# - Use query-aware compression for RAG pipelines
# - Compress chat histories while preserving system prompts
# - Estimate cost savings across different models
# - Customize the compressor for your specific use case
#
# For more examples, see the `examples/` directory.
# For the full API reference, see the [README](../README.md).

# %%
print("\n*** Demo complete! Star us on GitHub: https://github.com/Thanatos9404/context-compressor")
