"""The release workflow signs what it publishes, and only a published release can publish."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
)
BUILD = WORKFLOW["jobs"]["build"]
PUBLISH = WORKFLOW["jobs"]["publish"]


def _steps(job, uses_prefix):
    return [step for step in job["steps"] if step.get("uses", "").startswith(uses_prefix)]


def test_pull_requests_build_but_only_a_release_publishes():
    triggers = WORKFLOW[True]  # YAML 1.1 reads the bare key "on" as true
    assert set(triggers) == {"release", "pull_request", "workflow_dispatch"}
    assert triggers["release"] == {"types": ["published"]}
    assert "if" not in BUILD
    assert PUBLISH["if"] == "github.event_name == 'release'"
    assert PUBLISH["needs"] == "build"
    assert PUBLISH["environment"] == "pypi"


def test_only_the_publish_job_can_sign_or_write():
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert "permissions" not in BUILD
    assert PUBLISH["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }


def test_the_wheel_and_sdist_get_provenance_and_sbom_attestations():
    attest = _steps(PUBLISH, "actions/attest@")
    assert [step["with"]["subject-path"] for step in attest] == ["dist/*", "dist/*"]
    assert "sbom-path" not in attest[0]["with"]  # SLSA build provenance
    assert (
        attest[1]["with"]["sbom-path"] == "sbom/llmslim-${{ needs.build.outputs.version }}.cdx.json"
    )


def test_pypi_publishing_uploads_attestations():
    (publish,) = _steps(PUBLISH, "pypa/gh-action-pypi-publish@")
    assert publish["with"]["attestations"] is True
    assert "password" not in publish["with"]  # trusted publishing, no token
    names = [step.get("uses", "").split("@")[0] for step in PUBLISH["steps"]]
    assert names.index("actions/attest") < names.index("pypa/gh-action-pypi-publish")


def test_the_sbom_is_built_validated_and_attached():
    runs = "\n".join(step.get("run", "") for step in BUILD["steps"])
    assert "cyclonedx-py environment" in runs and "--validate" in runs
    assert "sbom/llmslim-${VERSION}.cdx.json" in runs
    (upload,) = _steps(BUILD, "actions/upload-artifact@")
    assert "sbom/" in upload["with"]["path"] and "dist/" in upload["with"]["path"]
    (release,) = _steps(PUBLISH, "softprops/action-gh-release@")
    assert "sbom/*.cdx.json" in release["with"]["files"]


def test_the_tag_check_runs_only_for_a_release():
    (check,) = [step for step in BUILD["steps"] if step["name"].startswith("Verify release tag")]
    assert check["if"] == "github.event_name == 'release'"
