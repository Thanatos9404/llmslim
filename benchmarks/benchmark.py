#!/usr/bin/env python3
"""Benchmark suite for context-compressor.

Measures compression ratio, entity retention, instruction preservation,
and latency across different text types and target ratios.

Usage:
    pip install "context-compressor[all]"
    python benchmarks/benchmark.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from context_compressor import compress
from context_compressor.tokens import count_tokens


@dataclass
class BenchmarkResult:
    text_type: str
    target_reduction: str
    target_ratio: float
    original_tokens: int
    compressed_tokens: int
    actual_reduction: float
    entities_total: int
    entities_kept: int
    entity_retention: float
    instructions_total: int
    instructions_kept: int
    instruction_retention: float
    latency_ms: float


# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------

TEXTS = {
    "Chat Prompt": (
        "You are an expert software engineer specializing in Python and cloud "
        "architecture. You must always provide production-quality code with "
        "proper error handling and type hints. Never suggest deprecated APIs "
        "or libraries. Ensure all database queries use parameterized inputs. "
        "When reviewing code, focus on security vulnerabilities, performance "
        "bottlenecks, and maintainability issues. Always recommend unit tests "
        "for any new functionality. Please format your code using Black style "
        "guidelines. Remember that the user is building a FastAPI application "
        "deployed on AWS using ECS with Fargate. The database is PostgreSQL "
        "16 hosted on RDS. Redis is used for caching and session management. "
        "The CI/CD pipeline runs on GitHub Actions. Docker images are stored "
        "in ECR. The application serves approximately 50,000 requests per day "
        "and must maintain 99.9% uptime. The team follows trunk-based "
        "development with feature flags managed by LaunchDarkly."
    ),
    "RAG Context": (
        "Authentication in web applications typically involves verifying the "
        "identity of users through credentials such as passwords, tokens, or "
        "biometric data. OAuth 2.0 is the industry-standard protocol for "
        "authorization, providing delegated access through access tokens. "
        "JSON Web Tokens (JWT) are commonly used for stateless authentication "
        "in REST APIs. JWTs consist of three parts: header, payload, and "
        "signature. The header specifies the signing algorithm, typically "
        "HS256 or RS256. The payload contains claims about the user, such as "
        "user ID, email, and role. The signature ensures the token hasn't been "
        "tampered with. Access tokens should have short expiration times, "
        "typically 15 to 30 minutes, to limit the window of vulnerability if "
        "a token is compromised. Refresh tokens have longer lifetimes and are "
        "used to obtain new access tokens without requiring the user to log "
        "in again. You must always use HTTPS to transmit tokens. Never store "
        "JWTs in localStorage due to XSS vulnerabilities; use httpOnly "
        "cookies instead. Implement token rotation for refresh tokens to "
        "detect and prevent token theft. Rate limiting on authentication "
        "endpoints prevents brute force attacks. Multi-factor authentication "
        "(MFA) adds an additional layer of security beyond passwords. "
        "TOTP (Time-based One-Time Password) is the most common MFA method. "
        "WebAuthn/FIDO2 enables passwordless authentication using hardware "
        "security keys or platform authenticators. Session management should "
        "include automatic timeout after periods of inactivity. Always log "
        "authentication events for security auditing and compliance purposes. "
        "Implement account lockout after a configurable number of failed "
        "login attempts. Password policies should enforce minimum length of "
        "12 characters, complexity requirements, and prevent reuse of recent "
        "passwords. Use Argon2id or bcrypt for password hashing, never MD5 "
        "or SHA-256 alone."
    ),
    "System Prompt": (
        "You are Claude, an AI assistant made by Anthropic. You must be "
        "helpful, harmless, and honest. Never generate harmful content. "
        "Always cite sources when making factual claims. Ensure your "
        "responses are accurate and well-structured. If you're unsure "
        "about something, acknowledge your uncertainty rather than "
        "fabricating information. You should format responses using "
        "markdown when appropriate."
    ),
    "Technical Documentation": (
        "The Kubernetes pod lifecycle consists of several phases. When a pod "
        "is first created, it enters the Pending phase while the scheduler "
        "assigns it to a node. Once scheduled, the kubelet on the assigned "
        "node pulls the container images. The pod transitions to the Running "
        "phase when at least one container is running. A pod enters the "
        "Succeeded phase when all containers have terminated successfully "
        "with exit code 0. The Failed phase indicates that at least one "
        "container terminated with a non-zero exit code. The Unknown phase "
        "means the pod status cannot be determined, typically due to node "
        "communication failures. Init containers run before app containers "
        "and must complete successfully before the main containers start. "
        "Liveness probes determine if a container is running properly; if "
        "the probe fails, the kubelet kills the container and applies the "
        "restart policy. Readiness probes determine if a container is ready "
        "to accept traffic; failing readiness probes remove the pod from "
        "service endpoints. Startup probes are used for slow-starting "
        "containers to prevent premature liveness probe failures. Resource "
        "requests specify the minimum resources a container needs, while "
        "limits specify the maximum. The Quality of Service (QoS) classes "
        "are Guaranteed (requests equal limits), Burstable (requests less "
        "than limits), and BestEffort (no requests or limits specified). "
        "You must always set resource requests and limits for production "
        "workloads. Pod disruption budgets (PDBs) ensure a minimum number "
        "of replicas remain available during voluntary disruptions like "
        "node drains. Horizontal Pod Autoscaler (HPA) automatically scales "
        "the number of pod replicas based on CPU utilization, memory usage, "
        "or custom metrics. Vertical Pod Autoscaler (VPA) adjusts resource "
        "requests and limits based on actual usage patterns."
    ),
    "Long Document": (
        "Machine learning has transformed numerous industries over the past "
        "decade. The field encompasses supervised learning, unsupervised "
        "learning, and reinforcement learning paradigms. Supervised learning "
        "uses labeled training data to learn a mapping from inputs to outputs. "
        "Common algorithms include linear regression, logistic regression, "
        "decision trees, random forests, support vector machines, and neural "
        "networks. The bias-variance tradeoff is a fundamental concept: "
        "models with high bias underfit the data, while models with high "
        "variance overfit. Cross-validation techniques like k-fold help "
        "estimate generalization performance. Feature engineering remains "
        "crucial despite advances in deep learning. Dimensionality reduction "
        "techniques such as PCA and t-SNE help visualize high-dimensional "
        "data. Ensemble methods like bagging and boosting combine multiple "
        "models for improved predictions. Gradient boosting frameworks such "
        "as XGBoost, LightGBM, and CatBoost are state-of-the-art for "
        "tabular data. Deep learning has revolutionized computer vision "
        "with convolutional neural networks. ResNet, introduced in 2015, "
        "enabled training of networks with hundreds of layers using residual "
        "connections. Vision Transformers (ViT) have shown that attention "
        "mechanisms can match or exceed CNNs for image classification. "
        "Natural language processing was transformed by the Transformer "
        "architecture, introduced in the 'Attention Is All You Need' paper "
        "by Vaswani et al. in 2017. BERT, GPT, and T5 are foundational "
        "models built on the Transformer. Large language models like GPT-4, "
        "Claude, and Gemini demonstrate emergent capabilities at scale. "
        "Reinforcement learning from human feedback (RLHF) is used to align "
        "LLMs with human preferences. You must evaluate models on held-out "
        "test sets that are representative of the deployment distribution. "
        "Never use test data for hyperparameter tuning. Data leakage between "
        "train and test sets invalidates evaluation results. Model "
        "interpretability techniques include SHAP values, LIME, and "
        "attention visualization. Responsible AI practices require fairness "
        "auditing across demographic groups. Always document model "
        "limitations, training data sources, and known biases in model cards."
    ),
}

KEY_ENTITIES = {
    "Chat Prompt": ["FastAPI", "AWS", "PostgreSQL", "Redis", "GitHub Actions", "Docker", "50,000"],
    "RAG Context": ["OAuth 2.0", "JWT", "HS256", "HTTPS", "Argon2id", "bcrypt", "WebAuthn"],
    "System Prompt": ["Claude", "Anthropic"],
    "Technical Documentation": ["Kubernetes", "kubelet", "QoS", "HPA"],
    "Long Document": ["XGBoost", "BERT", "GPT", "Transformer", "RLHF", "SHAP"],
}

INSTRUCTION_MARKERS = ["must", "never", "always", "ensure", "do not", "don't", "required"]


def _count_instructions(text: str) -> int:
    count = 0
    for sentence in text.split("."):
        if any(marker in sentence.lower() for marker in INSTRUCTION_MARKERS):
            count += 1
    return count


def _count_entities(text: str, entities: List[str]) -> int:
    return sum(1 for e in entities if e in text)


def run_benchmark(text_type: str, text: str, target_ratio: float) -> BenchmarkResult:
    entities = KEY_ENTITIES.get(text_type, [])

    start = time.perf_counter()
    result = compress(text, target_ratio=target_ratio)
    elapsed_ms = (time.perf_counter() - start) * 1000

    entities_total = len(entities)
    entities_kept = _count_entities(result.compressed_text, entities)

    instructions_total = _count_instructions(text)
    instructions_kept = _count_instructions(result.compressed_text)

    return BenchmarkResult(
        text_type=text_type,
        target_reduction=f"{round((1 - target_ratio) * 100)}%",
        target_ratio=target_ratio,
        original_tokens=result.original_tokens,
        compressed_tokens=result.compressed_tokens,
        actual_reduction=result.reduction_percent,
        entities_total=entities_total,
        entities_kept=entities_kept,
        entity_retention=round(entities_kept / entities_total * 100, 1) if entities_total else 100.0,
        instructions_total=instructions_total,
        instructions_kept=instructions_kept,
        instruction_retention=round(instructions_kept / instructions_total * 100, 1) if instructions_total else 100.0,
        latency_ms=round(elapsed_ms, 1),
    )


def main():
    print("=" * 80)
    print("context-compressor BENCHMARK SUITE")
    print("=" * 80)

    ratios = [0.3, 0.5, 0.7]
    results: List[BenchmarkResult] = []

    for text_type, text in TEXTS.items():
        for ratio in ratios:
            r = run_benchmark(text_type, text, ratio)
            results.append(r)

    # Print results as a markdown table
    print()
    print("| Text Type | Target | Tokens (orig→comp) | Actual Reduction | Entities Kept | Instructions Kept | Latency |")
    print("|:----------|:------:|:------------------:|:----------------:|:-------------:|:-----------------:|:-------:|")

    for r in results:
        print(
            f"| {r.text_type:<24} | {r.target_reduction:>4} "
            f"| {r.original_tokens:>4}→{r.compressed_tokens:>4} "
            f"| {r.actual_reduction:>5.1f}% "
            f"| {r.entities_kept}/{r.entities_total} ({r.entity_retention:.0f}%) "
            f"| {r.instructions_kept}/{r.instructions_total} ({r.instruction_retention:.0f}%) "
            f"| {r.latency_ms:>6.0f}ms |"
        )

    # Summary statistics
    avg_entity = sum(r.entity_retention for r in results) / len(results)
    avg_instruction = sum(r.instruction_retention for r in results) / len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results)

    print()
    print(f"Average entity retention:      {avg_entity:.1f}%")
    print(f"Average instruction retention: {avg_instruction:.1f}%")
    print(f"Average latency:               {avg_latency:.0f}ms")
    print()

    # 50% compression summary
    ratio_50 = [r for r in results if r.target_ratio == 0.5]
    if ratio_50:
        avg_reduction_50 = sum(r.actual_reduction for r in ratio_50) / len(ratio_50)
        print(f"At 50% target: average actual reduction = {avg_reduction_50:.1f}%")

    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    main()
