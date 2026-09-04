"""Cross-host packaging checks for Codex and Claude Code."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "fhir-jira"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_both_marketplaces_expose_the_same_plugin() -> None:
    codex = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    claude = load_json(ROOT / ".claude-plugin" / "marketplace.json")

    assert codex["name"] == claude["name"] == "fhir-jira-toolkit"
    assert [entry["name"] for entry in codex["plugins"]] == ["fhir-jira"]
    assert [entry["name"] for entry in claude["plugins"]] == ["fhir-jira"]
    assert codex["plugins"][0]["source"]["path"] == "./plugins/fhir-jira"
    assert claude["plugins"][0]["source"] == "./plugins/fhir-jira"


def test_both_manifests_share_identity_and_version() -> None:
    expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    codex = load_json(PLUGIN / ".codex-plugin" / "plugin.json")
    claude = load_json(PLUGIN / ".claude-plugin" / "plugin.json")

    assert codex["name"] == claude["name"] == "fhir-jira"
    assert codex["version"] == claude["version"] == expected_version
    assert codex["skills"] == "./skills/"

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert project_version is not None
    assert project_version.group(1) == expected_version


def test_codex_skill_entrypoints_and_shared_workflow_are_packaged() -> None:
    expected = {"fhir-jira", "fhir-jira-batch", "fhir-jira-workflow"}
    packaged = {
        path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md")
    }

    assert expected <= packaged

    for entrypoint in ("fhir-jira", "fhir-jira-batch"):
        text = (PLUGIN / "skills" / entrypoint / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "$ARGUMENTS" in text

    workflow = (
        PLUGIN / "skills" / "fhir-jira-workflow" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "PLUGIN_ROOT" in workflow
    assert "CLAUDE_PLUGIN_ROOT" in workflow
    assert "FHIR_JIRA_PLUGIN_ROOT" in workflow


def test_manifest_paths_stay_inside_the_plugin() -> None:
    codex = load_json(PLUGIN / ".codex-plugin" / "plugin.json")

    for field in ("skills", "hooks", "mcpServers", "apps"):
        value = codex.get(field)
        if not isinstance(value, str):
            continue
        assert value.startswith("./")
        assert ".." not in Path(value).parts
        assert (PLUGIN / value).exists()


def test_published_output_qa_is_required_for_single_and_batch_flows() -> None:
    workflow = (
        PLUGIN / "skills" / "fhir-jira-workflow" / "SKILL.md"
    ).read_text(encoding="utf-8")
    single = (PLUGIN / "skills" / "fhir-jira" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    batch = (PLUGIN / "skills" / "fhir-jira-batch" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert (
        "Verify the published output satisfies each ticket (required)" in workflow
    )
    assert "browser absence" in workflow
    assert "does not waive semantic QA" in workflow
    assert "do not substitute one group-level spot check" in workflow
    assert "published-output QA verdict" in single
    assert "one published-output QA verdict per" in batch


def test_fhir_core_changes_require_categorized_ballot_impact_notes() -> None:
    workflow = (
        PLUGIN / "skills" / "fhir-jira-workflow" / "SKILL.md"
    ).read_text(encoding="utf-8")
    authoring = (
        PLUGIN
        / "skills"
        / "fhir-jira-workflow"
        / "references"
        / "fhir-authoring.md"
    ).read_text(encoding="utf-8")
    jira_fields = (
        PLUGIN
        / "skills"
        / "fhir-jira-workflow"
        / "references"
        / "jira-fields.md"
    ).read_text(encoding="utf-8")

    for text in (workflow, authoring, jira_fields):
        assert "Change Impact" in text
        assert "Non-compatible" in text
        assert "Compatible substantive" in text
        assert "Non-substantive" in text

    assert "module cross-reference" in workflow
    assert "appears exactly once" in authoring
    assert "do not create a parallel `stu-note`" in workflow
    assert "Do not create a parallel `stu-note`" in authoring
