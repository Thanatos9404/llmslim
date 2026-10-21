"""The Claude Code and Codex plugins, Gemini CLI extension and install links: valid, in step with the package."""

import base64
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
    # Claude Code reads "strict" per entry. The HOL plugin scanner looks for it at the top level.
    assert entry["strict"] is True
    assert marketplace["strict"] is True


def test_versions_match_the_package():
    assert _json(PLUGIN / ".claude-plugin" / "plugin.json")["version"] == llmslim.__version__
    assert _json(PLUGIN / ".codex-plugin" / "plugin.json")["version"] == llmslim.__version__
    server = _json(ROOT / "server.json")
    assert server["version"] == llmslim.__version__
    assert server["packages"][0]["version"] == llmslim.__version__
    assert _json(ROOT / "gemini-extension.json")["version"] == llmslim.__version__


def test_mcp_server_runs_the_published_package():
    # Directories reject a version range ("unpinned uvx launcher"), so the package is pinned to this release.
    expected = {
        "command": "uvx",
        "args": ["--from", f"llmslim[mcp]=={llmslim.__version__}", "llmslim", "mcp"],
    }
    assert _json(PLUGIN / ".mcp.json")["mcpServers"] == {"llmslim": expected}
    assert _json(ROOT / "gemini-extension.json")["mcpServers"] == {"llmslim": expected}
    # The Codex manifest starts the same pinned server from the same file.
    assert _json(PLUGIN / ".codex-plugin" / "plugin.json")["mcpServers"] == "./.mcp.json"


def test_codex_plugin_manifest():
    # Fields the awesome-codex-plugins validator requires.
    manifest = _json(PLUGIN / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == "llmslim"
    for field in ("description", "repository", "license"):
        assert manifest[field]
    assert manifest["interface"]["displayName"]
    assert manifest["interface"]["shortDescription"]


def test_plugin_ships_its_license_and_security_policy():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (PLUGIN / "LICENSE").read_text(encoding="utf-8") == license_text
    assert "## Reporting a vulnerability" in (PLUGIN / "SECURITY.md").read_text(encoding="utf-8")


def test_gemini_extension_manifest():
    extension = _json(ROOT / "gemini-extension.json")
    assert extension["name"] == "llmslim"
    assert extension["description"]


def test_plugin_readme_is_long_enough_for_the_directory():
    # The Claude plugin directory needs a README of at least 40 words, not counting code blocks.
    text = (PLUGIN / "README.md").read_text(encoding="utf-8")
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    assert len(prose.split()) >= 40
    assert f"llmslim[mcp]=={llmslim.__version__}" in text


def test_readme_install_links_run_this_release():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    hosts = {"vscode.dev", "cursor.com", "lmstudio.ai", "goose-docs.ai", "kiro.dev"}
    links = [
        link
        for link in re.findall(r"\)\]\((https://[^)\s]+)\)", readme)
        if urlsplit(link).hostname in hosts
    ]
    assert {urlsplit(link).hostname for link in links} == hosts
    for link in links:
        query = parse_qs(urlsplit(link).query)
        if "cmd" in query:  # Goose passes the command as cmd and arg parameters
            command = [query["cmd"][0], *query["arg"]]
        else:  # JSON, or base64 JSON for Cursor and LM Studio
            raw = query["config"][0]
            config = json.loads(raw if raw.startswith("{") else base64.b64decode(raw))
            command = [config["command"], *config["args"]]
        assert command == [
            "uvx",
            "--from",
            f"llmslim[mcp]=={llmslim.__version__}",
            "llmslim",
            "mcp",
        ]


def test_skills_have_a_name_and_description():
    skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    assert [path.parent.name for path in skills] == ["savings", "wrap-claude"]
    for path in skills:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        frontmatter = text.split("---\n", 2)[1]
        assert f"\nname: {path.parent.name}\n" in "\n" + frontmatter
        assert "\ndescription: " in "\n" + frontmatter
