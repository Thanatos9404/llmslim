#!/usr/bin/env python3
"""Example: Compressing long documents (research papers, legal docs, reports).

When you need to feed a long document into an LLM for summarization,
Q&A, or analysis, llmslim can cut it down to fit within
context windows while preserving the key facts, entities, and structure.

Usage:
    pip install "llmslim[all]"
    python examples/long_document_example.py
"""

from llmslim import compress, estimate_cost_savings

# A realistic long document (~2,500 tokens) simulating a technical report
LONG_DOCUMENT = """
# Quarterly Engineering Report — Q4 2025

## Executive Summary

This report covers the engineering team's progress during Q4 2025, including
key milestones achieved, technical debt addressed, and plans for Q1 2026.
The team shipped 47 features across 3 product lines, reduced P1 incident
response time by 38%, and migrated 85% of services to Kubernetes.

## Infrastructure Modernization

The infrastructure team completed Phase 2 of the cloud migration initiative.
We migrated 34 microservices from EC2 instances to Amazon EKS (Elastic
Kubernetes Service) during this quarter. The remaining 6 services are
scheduled for Q1 2026 migration. Container orchestration has reduced our
infrastructure costs by approximately $47,000 per month. Average deployment
time decreased from 45 minutes to 8 minutes. We implemented GitOps
workflows using ArgoCD for all Kubernetes deployments. The team also
established a service mesh using Istio for inter-service communication,
enabling mutual TLS, traffic management, and observability without
application code changes.

Database performance was a major focus area. We migrated the primary
PostgreSQL database from version 12 to version 16, gaining significant
performance improvements in parallel query execution and logical
replication. The migration was completed with zero downtime using pglogical.
Read replica latency decreased from 800ms to under 50ms. We also
implemented connection pooling with PgBouncer, reducing database connection
overhead by 60%. The analytics database was moved to ClickHouse, resulting
in 15x faster analytical queries compared to the previous PostgreSQL
implementation.

## Platform Engineering

The platform team launched the internal developer portal built on Backstage.
The portal provides service catalogs, documentation, and self-service
infrastructure provisioning. Developer satisfaction scores increased from
3.2 to 4.1 (out of 5) after the portal launch. The team also built a
custom Terraform provider for our internal services, reducing infrastructure
provisioning time from days to minutes.

CI/CD pipeline improvements included migration from Jenkins to GitHub
Actions for all 89 repositories. Build times decreased by an average of
42%. We implemented mandatory security scanning using Snyk and SonarQube
in all pipelines. Code coverage requirements were raised from 60% to 80%
for all new code. The team also introduced preview environments for every
pull request, enabling faster code reviews and QA cycles.

## API Platform

The API team shipped version 3.0 of the public API, introducing GraphQL
alongside the existing REST endpoints. The GraphQL gateway handles an
average of 2.3 million requests per day with a P99 latency of 120ms.
Rate limiting was enhanced with a sliding window algorithm, replacing
the previous fixed window approach. This reduced false positives by 73%
while maintaining protection against abuse.

API documentation was migrated to a new portal using Redocly, with
auto-generated SDKs for Python, JavaScript, Go, and Java. Customer-reported
API issues decreased by 54% after the documentation improvement. We also
introduced API versioning via URL path (v3/) and implemented a 12-month
deprecation policy for older versions. Partners must migrate to v3 by
December 2026.

## Security Improvements

The security team completed SOC 2 Type II certification in November 2025.
We implemented zero-trust network architecture across all production
environments. All internal services now require mutual TLS for communication.
The team deployed CrowdStrike Falcon for endpoint detection and response
across all servers. Vulnerability remediation SLA was reduced from 30 days
to 7 days for critical vulnerabilities. We conducted 4 penetration tests
with external firms, identifying and remediating 12 findings (3 high, 5
medium, 4 low severity). Employee security awareness training completion
rate reached 98%.

## Machine Learning Operations

The ML team established a feature store using Feast, serving 23 production
models. Model deployment time decreased from 2 weeks to 2 days using our
new MLOps pipeline built on Kubeflow. A/B testing infrastructure was
implemented, enabling data-driven model rollouts. The recommendation
engine achieved a 12% improvement in click-through rate after deploying
the new transformer-based model. Model monitoring with Evidently AI
detected 3 instances of data drift before they impacted production metrics.

## Key Metrics

- Uptime: 99.97% (target: 99.95%)
- Mean Time to Recovery (MTTR): 14 minutes (down from 23 minutes)
- Deployment frequency: 47 deploys/week (up from 31)
- Change failure rate: 2.1% (down from 4.7%)
- P1 incidents: 8 (down from 13 in Q3)
- Customer satisfaction (CSAT): 4.4/5.0
- Engineering headcount: 67 (hired 12, attrition 3)

## Q1 2026 Priorities

1. Complete remaining 6 service migrations to Kubernetes
2. Launch real-time event streaming platform using Apache Kafka
3. Implement automated chaos engineering with Gremlin
4. Migrate authentication to passwordless (WebAuthn/FIDO2)
5. Achieve ISO 27001 certification
6. Deploy LLM-powered internal knowledge base
7. Reduce cloud costs by an additional 15% through reserved instances
"""


def main():
    print("=" * 60)
    print("LONG DOCUMENT COMPRESSION EXAMPLE")
    print("=" * 60)

    # --- Compress at different ratios ---
    for ratio in [0.7, 0.5, 0.3]:
        result = compress(LONG_DOCUMENT, target_ratio=ratio)
        reduction_target = round((1 - ratio) * 100)

        print(f"\n--- Target: {reduction_target}% reduction (ratio={ratio}) ---")
        print(result.summary())

        # Check if key entities survived
        key_entities = [
            "Kubernetes",
            "PostgreSQL",
            "SOC 2",
            "GraphQL",
            "99.97%",
            "Q1 2026",
        ]
        preserved = [e for e in key_entities if e in result.compressed_text]
        print(
            f"  Key entities preserved: {len(preserved)}/{len(key_entities)} "
            f"({', '.join(preserved)})"
        )

    # --- Detailed view of 50% compression ---
    print("\n" + "=" * 60)
    print("DETAILED 50% COMPRESSION")
    print("=" * 60)
    result = compress(LONG_DOCUMENT, target_ratio=0.5)

    print("\n--- Compressed Document ---\n")
    print(result.compressed_text)

    # --- Cost savings for a document processing pipeline ---
    print("\n--- Cost Savings for Document Processing ---")
    print("Scenario: Processing 5,000 documents/day through GPT-5\n")

    for model in ["gpt-5", "gpt-5.4", "claude-opus-4.8"]:
        est = estimate_cost_savings(
            result.original_tokens,
            result.compressed_tokens,
            model=model,
            requests_per_day=5_000,
        )
        print(f"  {est.model}:")
        print(f"    Daily:  ${est.daily_savings_usd:,.2f}")
        print(f"    Annual: ${est.annual_savings_usd:,.2f}")

    print("\n[OK] Long document compressed while preserving structure and key data!")


if __name__ == "__main__":
    main()
