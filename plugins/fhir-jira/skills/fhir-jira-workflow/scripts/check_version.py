#!/usr/bin/env python3
"""Verify that the running FHIR JIRA plugin matches toolkit main."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


EXIT_NOT_LATEST = 10
EXIT_UNVERIFIED = 11
EXIT_INVALID_INSTALL = 12
DEFAULT_REPOSITORY = "jdlnolen/fhir-jira-toolkit"
DEFAULT_REF = "main"
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")


class VersionCheckError(RuntimeError):
    """Raised when a version cannot be read or trusted."""


def _read_manifest_version(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionCheckError(f"cannot read {path}: {exc}") from exc

    version = payload.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise VersionCheckError(f"invalid version in {path}")
    return version


def installed_version(plugin_root: Path) -> str:
    """Return the installed version after checking both host manifests."""

    manifests = (
        plugin_root / ".codex-plugin" / "plugin.json",
        plugin_root / ".claude-plugin" / "plugin.json",
    )
    versions = {path: _read_manifest_version(path) for path in manifests}
    unique = set(versions.values())
    if len(unique) != 1:
        detail = ", ".join(f"{path}: {version}" for path, version in versions.items())
        raise VersionCheckError(f"host manifest versions disagree ({detail})")
    return unique.pop()


def latest_version(repository: str, ref: str) -> str:
    """Read VERSION from the configured GitHub repository and ref."""

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise VersionCheckError(f"invalid GitHub repository: {repository}")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", ref):
        raise VersionCheckError(f"invalid Git ref: {ref}")

    endpoint = f"repos/{repository}/contents/VERSION?ref={ref}"
    try:
        completed = subprocess.run(
            [
                "gh",
                "api",
                "--method",
                "GET",
                "-H",
                "Accept: application/vnd.github.raw+json",
                endpoint,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise VersionCheckError("gh is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise VersionCheckError("GitHub version lookup timed out") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise VersionCheckError(f"GitHub version lookup failed{suffix}")

    version = completed.stdout.strip()
    if not VERSION_RE.fullmatch(version):
        raise VersionCheckError("GitHub VERSION response was empty or invalid")
    return version


def release_line(version: str) -> str:
    """Ignore SemVer build metadata such as a local Codex cachebuster."""

    return version.split("+", 1)[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check the running FHIR JIRA plugin against toolkit main."
    )
    parser.add_argument(
        "--plugin-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Path to the installed fhir-jira plugin root.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument(
        "--latest-version",
        help="Use an explicit latest version instead of GitHub (for tests).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        running = installed_version(args.plugin_root.resolve())
    except VersionCheckError as exc:
        print(f"INVALID INSTALL: {exc}", file=sys.stderr)
        return EXIT_INVALID_INSTALL

    try:
        latest = args.latest_version or latest_version(args.repo, args.ref)
        if not VERSION_RE.fullmatch(latest):
            raise VersionCheckError("latest version was empty or invalid")
    except VersionCheckError as exc:
        print(
            f"VERSION UNVERIFIED: running {running}; {exc}",
            file=sys.stderr,
        )
        return EXIT_UNVERIFIED

    if release_line(running) != release_line(latest):
        print(
            "VERSION NOT CURRENT: "
            f"running {running}; latest {latest} from {args.repo}@{args.ref}",
            file=sys.stderr,
        )
        return EXIT_NOT_LATEST

    print(
        f"FHIR JIRA plugin {running} is current with {args.repo}@{args.ref}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
