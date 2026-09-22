"""Tests for the FHIR JIRA plugin version preflight."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import check_version


def write_manifests(plugin_root: Path, version: str) -> None:
    for host in (".codex-plugin", ".claude-plugin"):
        directory = plugin_root / host
        directory.mkdir(parents=True)
        (directory / "plugin.json").write_text(
            json.dumps({"name": "fhir-jira", "version": version}),
            encoding="utf-8",
        )


def test_current_version_passes(tmp_path: Path, capsys) -> None:
    write_manifests(tmp_path, "1.2.3+codex.local-test")

    result = check_version.main(
        [
            "--plugin-root",
            str(tmp_path),
            "--latest-version",
            "1.2.3",
        ]
    )

    assert result == 0
    assert "is current" in capsys.readouterr().out


def test_noncurrent_version_stops(tmp_path: Path, capsys) -> None:
    write_manifests(tmp_path, "1.2.2")

    result = check_version.main(
        [
            "--plugin-root",
            str(tmp_path),
            "--latest-version",
            "1.2.3",
        ]
    )

    assert result == check_version.EXIT_NOT_LATEST
    assert "running 1.2.2; latest 1.2.3" in capsys.readouterr().err


def test_manifest_mismatch_is_an_invalid_install(tmp_path: Path, capsys) -> None:
    write_manifests(tmp_path, "1.2.3")
    claude = tmp_path / ".claude-plugin" / "plugin.json"
    claude.write_text(
        json.dumps({"name": "fhir-jira", "version": "1.2.2"}),
        encoding="utf-8",
    )

    result = check_version.main(
        [
            "--plugin-root",
            str(tmp_path),
            "--latest-version",
            "1.2.3",
        ]
    )

    assert result == check_version.EXIT_INVALID_INSTALL
    assert "host manifest versions disagree" in capsys.readouterr().err


def test_github_lookup_uses_argv_and_raw_content(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="2.0.0\n", stderr="")

    monkeypatch.setattr(check_version.subprocess, "run", fake_run)

    assert check_version.latest_version("owner/repo", "main") == "2.0.0"
    argv, kwargs = calls[0]
    assert argv == [
        "gh",
        "api",
        "--method",
        "GET",
        "-H",
        "Accept: application/vnd.github.raw+json",
        "repos/owner/repo/contents/VERSION?ref=main",
    ]
    assert kwargs["timeout"] == 30


def test_failed_github_lookup_is_unverified(tmp_path: Path, monkeypatch, capsys) -> None:
    write_manifests(tmp_path, "1.2.3")

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="offline")

    monkeypatch.setattr(check_version.subprocess, "run", fake_run)

    result = check_version.main(["--plugin-root", str(tmp_path)])

    assert result == check_version.EXIT_UNVERIFIED
    assert "VERSION UNVERIFIED" in capsys.readouterr().err
