"""Tests for llmslim.rewrite.templates — template builders and resolver."""

from __future__ import annotations

import pytest

from llmslim.rewrite.templates import (
    RewriteTemplate,
    TemplateResolver,
    build_chat_template,
    build_code_template,
    build_documentation_template,
    build_general_template,
    build_rag_template,
    build_system_prompt_template,
)

# ─────────────────────────────────────────────────────────────────────
# RewriteTemplate
# ─────────────────────────────────────────────────────────────────────


class TestRewriteTemplate:
    def test_frozen(self):
        t = build_general_template()
        with pytest.raises(AttributeError):
            t.name = "changed"  # type: ignore[misc]

    def test_format_user_prompt(self):
        t = build_general_template()
        prompt = t.format_user_prompt(
            text="Hello world",
            target_ratio=0.5,
            constraints="Keep URLs.",
        )
        assert "Hello world" in prompt
        assert "50%" in prompt
        assert "Keep URLs." in prompt

    def test_format_user_prompt_defaults(self):
        t = build_general_template()
        prompt = t.format_user_prompt(text="Test text")
        assert "Test text" in prompt
        assert "50%" in prompt

    def test_format_user_prompt_target_percent(self):
        t = build_general_template()
        prompt = t.format_user_prompt(text="x", target_ratio=0.3)
        assert "70%" in prompt  # 1 - 0.3 = 0.7 = 70%


# ─────────────────────────────────────────────────────────────────────
# Builder functions
# ─────────────────────────────────────────────────────────────────────


class TestBuilders:
    """Each builder returns a complete, valid RewriteTemplate."""

    BUILDERS = [
        build_general_template,
        build_rag_template,
        build_chat_template,
        build_system_prompt_template,
        build_documentation_template,
        build_code_template,
    ]

    @pytest.mark.parametrize("builder", BUILDERS)
    def test_builder_returns_template(self, builder):
        t = builder()
        assert isinstance(t, RewriteTemplate)
        assert t.name
        assert t.version
        assert t.system_prompt
        assert t.user_prompt_template

    @pytest.mark.parametrize("builder", BUILDERS)
    def test_builder_version_override(self, builder):
        t = builder(version="42")
        assert t.version == "42"

    @pytest.mark.parametrize("builder", BUILDERS)
    def test_builder_template_has_placeholders(self, builder):
        t = builder()
        assert "{text}" in t.user_prompt_template
        assert "{constraints}" in t.user_prompt_template

    def test_all_templates_have_unique_names(self):
        names = [b().name for b in self.BUILDERS]
        assert len(names) == len(set(names))

    def test_system_prompt_template_preserves_instructions(self):
        t = build_system_prompt_template()
        assert "must" in t.system_prompt.lower()
        assert "never" in t.system_prompt.lower()


# ─────────────────────────────────────────────────────────────────────
# TemplateResolver
# ─────────────────────────────────────────────────────────────────────


class TestTemplateResolver:
    def test_resolve_by_name(self):
        resolver = TemplateResolver()
        t = resolver.resolve(name="general")
        assert t.name == "general"

    def test_resolve_by_content_type(self):
        resolver = TemplateResolver()
        t = resolver.resolve(content_type="rag_context")
        assert t.name == "rag_context"

    def test_resolve_content_type_chat(self):
        resolver = TemplateResolver()
        t = resolver.resolve(content_type="chat_conversation")
        assert t.name == "chat_history"

    def test_resolve_content_type_code(self):
        resolver = TemplateResolver()
        for ct in ("python", "javascript", "typescript", "sql"):
            t = resolver.resolve(content_type=ct)
            assert t.name == "code_context"

    def test_resolve_content_type_docs(self):
        resolver = TemplateResolver()
        for ct in ("markdown", "api_documentation", "technical_documentation"):
            t = resolver.resolve(content_type=ct)
            assert t.name == "documentation"

    def test_resolve_fallback_to_general(self):
        resolver = TemplateResolver()
        t = resolver.resolve()
        assert t.name == "general"

    def test_resolve_unknown_content_type_fallback(self):
        resolver = TemplateResolver()
        t = resolver.resolve(content_type="unknown_type_xyz")
        assert t.name == "general"

    def test_resolve_unknown_name_raises(self):
        resolver = TemplateResolver()
        with pytest.raises(ValueError, match="Unknown template 'nonexistent'"):
            resolver.resolve(name="nonexistent")

    def test_register_custom_template(self):
        resolver = TemplateResolver()
        custom = RewriteTemplate(
            name="my_custom",
            version="1",
            system_prompt="Custom system",
            user_prompt_template="Custom: {text} {constraints}",
        )
        resolver.register(custom)
        t = resolver.resolve(name="my_custom")
        assert t.name == "my_custom"
        assert t.system_prompt == "Custom system"

    def test_custom_overrides_builtin(self):
        resolver = TemplateResolver()
        custom_general = RewriteTemplate(
            name="general",
            version="99",
            system_prompt="Overridden",
            user_prompt_template="{text} {constraints}",
        )
        resolver.register(custom_general)
        t = resolver.resolve(name="general")
        assert t.version == "99"
        assert t.system_prompt == "Overridden"

    def test_list_templates(self):
        resolver = TemplateResolver()
        templates = resolver.list_templates()
        assert "general" in templates
        assert "rag_context" in templates
        assert "chat_history" in templates
        assert len(templates) >= 6

    def test_list_templates_includes_custom(self):
        resolver = TemplateResolver()
        custom = RewriteTemplate(
            name="extra",
            version="1",
            system_prompt="sys",
            user_prompt_template="{text} {constraints}",
        )
        resolver.register(custom)
        templates = resolver.list_templates()
        assert "extra" in templates

    def test_name_takes_precedence_over_content_type(self):
        """When both name and content_type are given, name wins."""
        resolver = TemplateResolver()
        t = resolver.resolve(name="code_context", content_type="rag_context")
        assert t.name == "code_context"
