"""The Claude Code plugin marketplace in this repo: valid manifests, versions in step with the package."""

import json
from pathlib import Path

import llmslim

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "llmslim"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marketplace_lists_the_plugin():
    marketplace = _json(ROOT / ".claude-plugin" / "marketplace.json")
    assert marketplace["name"] == "llmslim"
    assert marketplace["owner"]["name"]
    (entry,) = marketplace["plugins"]
    assert entry["name"] == "llmslim"
    assert (ROOT / entry["source"]).resolve() == PLUGIN


def test_versions_match_the_package():
    assert _json(PLUGIN / ".claude-plugin" / "plugin.json")["version"] == llmslim.__version__
    server = _json(ROOT / "server.json")
    assert server["version"] == llmslim.__version__
    assert server["packages"][0]["version"] == llmslim.__version__


def test_mcp_server_runs_the_published_package():
    server = _json(PLUGIN / ".mcp.json")["mcpServers"]["llmslim"]
    assert server["command"] == "uvx"
    assert server["args"][0] == "--from"
    assert server["args"][1].startswith("llmslim[mcp]")
    assert server["args"][2:] == ["llmslim", "mcp"]


def test_skills_have_a_description():
    skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    assert [path.parent.name for path in skills] == ["savings", "wrap-claude"]
    for path in skills:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        frontmatter = text.split("---\n", 2)[1]
        assert "\ndescription: " in "\n" + frontmatter
