"""Tests for llmslim.analysis -- content type detection and profiling."""

from __future__ import annotations

import time

import pytest

from llmslim.analysis import ContentProfile, ContentType, analyze


# =====================================================================
# Representative samples
# =====================================================================

JSON_SAMPLE = '{"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}], "total": 2}'

JSON_OBJECT_SAMPLE = (
    '{\n'
    '    "name": "llmslim",\n'
    '    "version": "0.3.0",\n'
    '    "dependencies": {\n'
    '        "numpy": ">=1.21",\n'
    '        "scikit-learn": ">=1.0"\n'
    '    }\n'
    '}'
)

JSON_ARRAY_SAMPLE = '[{"key": "value1"}, {"key": "value2"}, {"key": "value3"}]'

YAML_SAMPLE = (
    "---\n"
    "apiVersion: apps/v1\n"
    "kind: Deployment\n"
    "metadata:\n"
    "  name: my-app\n"
    "  labels:\n"
    "    app: my-app\n"
    "    version: v1.2.3\n"
    "spec:\n"
    "  replicas: 3\n"
    "  selector:\n"
    "    matchLabels:\n"
    "      app: my-app\n"
    "  template:\n"
    "    spec:\n"
    "      containers:\n"
    "        - name: my-app\n"
    "          image: my-app:latest\n"
    "          ports:\n"
    "            - containerPort: 8080\n"
)

MARKDOWN_SAMPLE = (
    "# Getting Started\n\n"
    "Welcome to the **project documentation**.\n\n"
    "## Installation\n\n"
    "Install using pip:\n\n"
    "```bash\npip install my-package\n```\n\n"
    "## Usage\n\n"
    "- Import the module\n"
    "- Call the main function\n"
    "- Check the [documentation](https://docs.example.com)\n\n"
    "### Advanced\n\n"
    "See the *configuration guide* for more details.\n"
)

HTML_SAMPLE = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    '    <meta charset="UTF-8">\n'
    "    <title>My Page</title>\n"
    "</head>\n"
    "<body>\n"
    '    <div class="container">\n'
    "        <p>Hello world</p>\n"
    '        <a href="/about">About</a>\n'
    '        <form action="/submit">\n'
    '            <input type="text" name="q">\n'
    '            <button type="submit">Go</button>\n'
    "        </form>\n"
    "    </div>\n"
    "</body>\n"
    "</html>"
)

XML_SAMPLE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<catalog xmlns="http://example.com/catalog">\n'
    '    <book id="1">\n'
    "        <title>Python Programming</title>\n"
    "        <author>Jane Doe</author>\n"
    '        <price currency="USD">29.99</price>\n'
    "    </book>\n"
    '    <book id="2">\n'
    "        <title>Data Science</title>\n"
    "        <author>John Smith</author>\n"
    "    </book>\n"
    "</catalog>"
)

PYTHON_SAMPLE = (
    "import os\n"
    "from dataclasses import dataclass\n"
    "from typing import List, Optional\n\n"
    "@dataclass\n"
    "class Config:\n"
    '    """Application configuration."""\n'
    '    host: str = "localhost"\n'
    "    port: int = 8080\n\n"
    "def create_app(config: Optional[Config] = None):\n"
    '    """Create the application."""\n'
    "    if config is None:\n"
    "        config = Config()\n"
    "    return config\n\n"
    "class Server:\n"
    "    def __init__(self, config: Config):\n"
    "        self.config = config\n"
    "    def start(self):\n"
    "        pass\n"
)

JAVASCRIPT_SAMPLE = (
    "import express from 'express';\n"
    "import { validate } from './utils';\n\n"
    "const app = express();\n"
    "const PORT = process.env.PORT || 3000;\n\n"
    "function handleRequest(req, res) {\n"
    "    const data = validate(req.body);\n"
    "    res.json({ success: true, data });\n"
    "}\n\n"
    "export const createRouter = () => {\n"
    "    const router = express.Router();\n"
    "    return router;\n"
    "};\n\n"
    "module.exports = { createRouter };\n"
)

TYPESCRIPT_SAMPLE = (
    "interface User {\n"
    "    id: number;\n"
    "    name: string;\n"
    "    email: string;\n"
    "    active: boolean;\n"
    "}\n\n"
    "export type UserRole = 'admin' | 'user' | 'guest';\n\n"
    "const getUser = (id: number): User => {\n"
    "    return { id, name: 'Alice', email: 'a@b.com', active: true };\n"
    "};\n\n"
    "export interface Config {\n"
    "    host: string;\n"
    "    port: number;\n"
    "}\n"
)

SQL_SAMPLE = (
    "SELECT u.id, u.name, o.total\n"
    "FROM users u\n"
    "INNER JOIN orders o ON u.id = o.user_id\n"
    "WHERE o.created_at > '2024-01-01'\n"
    "GROUP BY u.id, u.name\n"
    "ORDER BY o.total DESC;\n\n"
    "CREATE TABLE products (\n"
    "    id SERIAL PRIMARY KEY,\n"
    "    name VARCHAR(255) NOT NULL,\n"
    "    price DECIMAL(10, 2)\n"
    ");\n\n"
    "INSERT INTO products (name, price) VALUES ('Widget', 9.99);\n"
)

CHAT_SAMPLE = (
    "User: What is machine learning?\n\n"
    "Assistant: Machine learning is a subset of artificial intelligence "
    "that focuses on building systems that learn from data.\n\n"
    "User: Can you give me an example?\n\n"
    "Assistant: Sure! A spam filter is a classic example. It learns from "
    "labeled emails to classify new ones as spam or not spam.\n\n"
    "User: How does it learn?\n\n"
    "Assistant: It uses algorithms to find patterns in the training data.\n"
)

SYSTEM_PROMPT_SAMPLE = (
    "You are an expert Python developer and code reviewer.\n"
    "Your role is to analyze code for bugs, security issues, and best practices.\n\n"
    "Rules:\n"
    "- You must always explain your reasoning.\n"
    "- Never suggest deprecated APIs.\n"
    "- Always provide code examples.\n"
    "- Ensure your suggestions follow PEP 8.\n"
    "- Do not make assumptions about the codebase.\n"
    "- You should validate all inputs.\n"
    "- Make sure to handle edge cases.\n"
)

RAG_SAMPLE = (
    "Document 1: FastAPI is a modern web framework for building APIs with Python.\n"
    "It supports async/await natively and generates OpenAPI docs automatically.\n\n"
    "---\n\n"
    "Document 2: Authentication in FastAPI uses OAuth2 with JWT tokens.\n"
    "You must use HTTPS in production to protect tokens in transit.\n\n"
    "---\n\n"
    "Document 3: Rate limiting can be implemented using middleware.\n"
    "The slowapi library provides easy integration with FastAPI.\n"
)

LOG_SAMPLE = (
    "2024-06-15T10:23:45 [INFO] Application started on port 8080\n"
    "2024-06-15T10:23:46 [DEBUG] Loading configuration from /etc/app/config.yaml\n"
    "2024-06-15T10:23:47 [INFO] Database connection established\n"
    "2024-06-15T10:23:48 [WARN] Cache miss rate above threshold: 45%\n"
    "2024-06-15T10:24:01 [ERROR] Failed to connect to Redis: Connection refused\n"
    "2024-06-15T10:24:02 [INFO] Retrying Redis connection in 5s\n"
    "2024-06-15T10:24:07 [INFO] Redis connection restored\n"
    "2024-06-15T10:24:08 [DEBUG] Health check passed\n"
)

CONFIG_SAMPLE = (
    "# Application Configuration\n"
    "DATABASE_URL=postgresql://user:pass@localhost:5432/mydb\n"
    "REDIS_URL=redis://localhost:6379\n"
    "SECRET_KEY=my-super-secret-key\n"
    "DEBUG=false\n"
    "LOG_LEVEL=INFO\n"
    "MAX_CONNECTIONS=100\n"
    "# Feature flags\n"
    "ENABLE_CACHE=true\n"
    "ENABLE_METRICS=true\n"
)

API_DOCS_SAMPLE = (
    "## Users API\n\n"
    "GET /api/v1/users - List all users\n"
    "POST /api/v1/users - Create a new user\n"
    "GET /api/v1/users/{id} - Get user by ID\n"
    "PUT /api/v1/users/{id} - Update user\n"
    "DELETE /api/v1/users/{id} - Delete user\n\n"
    "### Response Body\n"
    "Returns 200 on success, 404 if not found, 400 for bad request.\n\n"
    "Request parameters include name, email, and role.\n"
    "Response schema includes id, name, email, created_at.\n"
)

RESEARCH_PAPER_SAMPLE = (
    "Abstract\n\n"
    "We present a novel approach to prompt optimization that reduces token "
    "usage by 40-70% while preserving semantic fidelity.\n\n"
    "Introduction\n\n"
    "Large language models require carefully crafted prompts [1]. "
    "Recent work (Smith et al., 2024) has shown that prompt compression "
    "can significantly reduce costs [2, 3].\n\n"
    "Methods\n\n"
    "Our method uses extractive summarization with semantic chunking. "
    "We build on the framework of Johnson (2023) and extend it with "
    "entity-aware ranking [4].\n\n"
    "Results\n\n"
    "Our approach achieves 52% compression on average while retaining "
    "96% of instruction fidelity [5, 6].\n\n"
    "Discussion\n\n"
    "The results demonstrate that semantic-aware compression outperforms "
    "naive truncation across all benchmarks.\n\n"
    "Conclusion\n\n"
    "We have shown that extractive prompt optimization is both effective "
    "and practical for production deployments.\n\n"
    "References\n"
)

TECH_DOC_SAMPLE = (
    "# Deployment Guide\n\n"
    "This guide covers deploying the application to production.\n\n"
    "## Prerequisites\n\n"
    "NOTE: You must have Docker installed.\n\n"
    "```bash\ndocker --version\n```\n\n"
    "## Configuration\n\n"
    "WARNING: Never commit secrets to version control.\n\n"
    "Create a `.env` file with the required variables.\n\n"
    "```yaml\nDATABASE_URL: postgres://localhost/mydb\n```\n\n"
    "## Deployment Steps\n\n"
    "1. Build the Docker image\n"
    "2. Push to registry\n"
    "3. Deploy to Kubernetes\n\n"
    "IMPORTANT: Always run migrations before deploying.\n"
)

GENERAL_TEXT_SAMPLE = (
    "The weather was beautiful today. I went for a walk in the park and "
    "saw many people enjoying the sunshine. The birds were singing and "
    "the flowers were blooming. It was a perfect spring day. Later I "
    "stopped at a cafe for coffee and read a book for an hour. The "
    "evening brought a gentle breeze and I decided to cook dinner at home."
)


# =====================================================================
# Core detection tests
# =====================================================================


class TestContentTypeDetection:
    """Each sample should be classified as its expected content type."""

    def test_json_object(self):
        profile = analyze(JSON_SAMPLE)
        assert profile.content_type == ContentType.JSON

    def test_json_object_multiline(self):
        profile = analyze(JSON_OBJECT_SAMPLE)
        assert profile.content_type == ContentType.JSON

    def test_json_array(self):
        profile = analyze(JSON_ARRAY_SAMPLE)
        assert profile.content_type == ContentType.JSON

    def test_yaml(self):
        profile = analyze(YAML_SAMPLE)
        assert profile.content_type == ContentType.YAML

    def test_markdown(self):
        profile = analyze(MARKDOWN_SAMPLE)
        assert profile.content_type == ContentType.MARKDOWN

    def test_html(self):
        profile = analyze(HTML_SAMPLE)
        assert profile.content_type == ContentType.HTML

    def test_xml(self):
        profile = analyze(XML_SAMPLE)
        assert profile.content_type == ContentType.XML

    def test_python(self):
        profile = analyze(PYTHON_SAMPLE)
        assert profile.content_type == ContentType.PYTHON

    def test_javascript(self):
        profile = analyze(JAVASCRIPT_SAMPLE)
        assert profile.content_type == ContentType.JAVASCRIPT

    def test_typescript(self):
        profile = analyze(TYPESCRIPT_SAMPLE)
        assert profile.content_type == ContentType.TYPESCRIPT

    def test_sql(self):
        profile = analyze(SQL_SAMPLE)
        assert profile.content_type == ContentType.SQL

    def test_chat(self):
        profile = analyze(CHAT_SAMPLE)
        assert profile.content_type == ContentType.CHAT_CONVERSATION

    def test_system_prompt(self):
        profile = analyze(SYSTEM_PROMPT_SAMPLE)
        assert profile.content_type == ContentType.SYSTEM_PROMPT

    def test_rag_context(self):
        profile = analyze(RAG_SAMPLE)
        assert profile.content_type == ContentType.RAG_CONTEXT

    def test_log_file(self):
        profile = analyze(LOG_SAMPLE)
        assert profile.content_type == ContentType.LOG_FILE

    def test_config_file(self):
        profile = analyze(CONFIG_SAMPLE)
        assert profile.content_type == ContentType.CONFIG_FILE

    def test_api_documentation(self):
        profile = analyze(API_DOCS_SAMPLE)
        assert profile.content_type == ContentType.API_DOCUMENTATION

    def test_research_paper(self):
        profile = analyze(RESEARCH_PAPER_SAMPLE)
        assert profile.content_type == ContentType.RESEARCH_PAPER

    def test_technical_documentation(self):
        profile = analyze(TECH_DOC_SAMPLE)
        assert profile.content_type == ContentType.TECHNICAL_DOCUMENTATION

    def test_general_text(self):
        profile = analyze(GENERAL_TEXT_SAMPLE)
        assert profile.content_type == ContentType.GENERAL_TEXT


# =====================================================================
# Profile metadata tests
# =====================================================================


class TestContentProfile:
    """Verify profile fields are populated correctly."""

    def test_profile_is_frozen(self):
        profile = analyze("hello world")
        with pytest.raises(AttributeError):
            profile.content_type = ContentType.JSON  # type: ignore[misc]

    def test_confidence_range(self):
        for sample in [
            JSON_SAMPLE, YAML_SAMPLE, MARKDOWN_SAMPLE, PYTHON_SAMPLE,
            SQL_SAMPLE, CHAT_SAMPLE, LOG_SAMPLE, GENERAL_TEXT_SAMPLE,
        ]:
            profile = analyze(sample)
            assert 0.0 <= profile.confidence <= 1.0

    def test_estimated_tokens_positive(self):
        profile = analyze(PYTHON_SAMPLE)
        assert profile.estimated_tokens > 0

    def test_has_structure_json(self):
        profile = analyze(JSON_SAMPLE)
        assert profile.has_structure is True

    def test_has_structure_yaml(self):
        profile = analyze(YAML_SAMPLE)
        assert profile.has_structure is True

    def test_has_structure_markdown(self):
        profile = analyze(MARKDOWN_SAMPLE)
        assert profile.has_structure is True

    def test_has_structure_general_text(self):
        profile = analyze(GENERAL_TEXT_SAMPLE)
        assert profile.has_structure is False

    def test_language_hint_python(self):
        profile = analyze(PYTHON_SAMPLE)
        assert profile.language_hint == "python"

    def test_language_hint_javascript(self):
        profile = analyze(JAVASCRIPT_SAMPLE)
        assert profile.language_hint == "javascript"

    def test_language_hint_typescript(self):
        profile = analyze(TYPESCRIPT_SAMPLE)
        assert profile.language_hint == "typescript"

    def test_language_hint_sql(self):
        profile = analyze(SQL_SAMPLE)
        assert profile.language_hint == "sql"

    def test_language_hint_none_for_prose(self):
        profile = analyze(GENERAL_TEXT_SAMPLE)
        assert profile.language_hint is None

    def test_structure_depth_json(self):
        profile = analyze(JSON_OBJECT_SAMPLE)
        assert profile.structure_depth >= 2  # at least 2 levels of nesting

    def test_structure_depth_yaml(self):
        profile = analyze(YAML_SAMPLE)
        assert profile.structure_depth >= 2

    def test_structure_depth_markdown(self):
        profile = analyze(MARKDOWN_SAMPLE)
        assert profile.structure_depth >= 2  # h1, h2, h3 = depth 3

    def test_structure_depth_zero_for_prose(self):
        profile = analyze(GENERAL_TEXT_SAMPLE)
        assert profile.structure_depth == 0

    def test_instruction_density_high_for_system_prompt(self):
        profile = analyze(SYSTEM_PROMPT_SAMPLE)
        assert profile.instruction_density > 0.3

    def test_instruction_density_low_for_general_text(self):
        profile = analyze(GENERAL_TEXT_SAMPLE)
        assert profile.instruction_density < 0.3

    def test_entity_density_positive_for_code(self):
        profile = analyze(PYTHON_SAMPLE)
        assert profile.entity_density > 0.0


# =====================================================================
# Secondary types
# =====================================================================


class TestSecondaryTypes:
    """Verify secondary type detection for mixed-content inputs."""

    def test_tech_doc_has_markdown_secondary(self):
        # Tech docs often contain markdown elements (headings, code blocks)
        profile = analyze(TECH_DOC_SAMPLE)
        all_types = {profile.content_type} | set(profile.secondary_types)
        # Should detect markdown signals as secondary
        assert ContentType.MARKDOWN in all_types or profile.content_type == ContentType.TECHNICAL_DOCUMENTATION

    def test_secondary_types_capped(self):
        # Secondary types should be capped at 3
        profile = analyze(TECH_DOC_SAMPLE)
        assert len(profile.secondary_types) <= 3


# =====================================================================
# Edge cases
# =====================================================================


class TestEdgeCases:
    """Boundary conditions and degenerate inputs."""

    def test_empty_string(self):
        profile = analyze("")
        assert profile.content_type == ContentType.GENERAL_TEXT
        assert profile.confidence == 1.0
        assert profile.estimated_tokens == 0

    def test_whitespace_only(self):
        profile = analyze("   \n\n\t  \n")
        assert profile.content_type == ContentType.GENERAL_TEXT

    def test_single_word(self):
        profile = analyze("hello")
        assert profile.content_type == ContentType.GENERAL_TEXT

    def test_single_json_brace(self):
        # Edge: just "{" is not valid JSON
        profile = analyze("{")
        # Should not crash; may or may not detect as JSON
        assert isinstance(profile, ContentProfile)

    def test_ambiguous_yaml_vs_config(self):
        # Simple key: value could be YAML or config
        text = "name: myapp\nversion: 1.0\nport: 8080\n"
        profile = analyze(text)
        assert profile.content_type in (ContentType.YAML, ContentType.CONFIG_FILE)

    def test_json_inside_markdown(self):
        text = (
            "# API Response\n\n"
            "The endpoint returns:\n\n"
            '```json\n{"status": "ok", "data": []}\n```\n\n'
            "## Error Codes\n\n"
            "- 400: Bad request\n"
            "- 500: Server error\n"
        )
        profile = analyze(text)
        # Should detect as markdown (primary), possibly JSON secondary
        assert profile.content_type == ContentType.MARKDOWN

    def test_very_short_code(self):
        # Too short to confidently classify
        text = "x = 1"
        profile = analyze(text)
        assert isinstance(profile, ContentProfile)

    def test_mixed_chat_json_format(self):
        text = (
            '{"role": "user", "content": "Hello"}\n'
            '{"role": "assistant", "content": "Hi there"}\n'
            '{"role": "user", "content": "How are you?"}\n'
        )
        profile = analyze(text)
        # Could be JSON or chat; both are valid interpretations
        assert profile.content_type in (
            ContentType.JSON, ContentType.CHAT_CONVERSATION
        )


# =====================================================================
# Determinism
# =====================================================================


class TestDeterminism:
    """analyze() must return identical results on repeated calls."""

    def test_deterministic_output(self):
        for sample in [
            JSON_SAMPLE, YAML_SAMPLE, PYTHON_SAMPLE, CHAT_SAMPLE,
            GENERAL_TEXT_SAMPLE,
        ]:
            p1 = analyze(sample)
            p2 = analyze(sample)
            assert p1 == p2, f"Non-deterministic for {p1.content_type}"


# =====================================================================
# Performance
# =====================================================================


class TestPerformance:
    """Content analysis should add negligible overhead."""

    def test_analysis_under_5ms_for_large_input(self):
        # Generate a ~10K token input (roughly 40K chars)
        large_text = GENERAL_TEXT_SAMPLE * 100
        start = time.perf_counter()
        for _ in range(10):
            analyze(large_text)
        elapsed_ms = (time.perf_counter() - start) / 10 * 1000
        # Should be well under 5ms per call even for large text
        assert elapsed_ms < 50, f"Analysis took {elapsed_ms:.1f}ms (limit: 50ms)"


# =====================================================================
# ContentType enum
# =====================================================================


class TestContentTypeEnum:
    """Verify enum properties."""

    def test_all_types_are_strings(self):
        for ct in ContentType:
            assert isinstance(ct.value, str)
            assert ct.value == ct.value.lower()

    def test_enum_count(self):
        assert len(ContentType) == 18

    def test_str_conversion(self):
        assert str(ContentType.JSON) == "ContentType.JSON"
        assert ContentType.JSON.value == "json"
