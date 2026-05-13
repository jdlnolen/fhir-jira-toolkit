#!/usr/bin/env python3
"""
SessionStart hook: check if a newer version of fhir-jira-toolkit is available.

Compares the local VERSION file against the VERSION file on GitHub main.
Writes a JSON envelope to stdout if an update is available. Fails silently
on any error (network timeout, missing file, etc.) — never blocks session start.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_REPO = "jdlnolen/fhir-jira-toolkit"
GITHUB_BRANCH = "main"
VERSION_PATH = "VERSION"
TIMEOUT = 5  # seconds — keep session start fast


def _read_local_version() -> str:
    """Read the local VERSION file, walking up from this script's location."""
    here = Path(__file__).resolve().parent
    # Walk up to find VERSION at the plugin root or marketplace root
    for p in [here.parent, here.parent.parent, here.parent.parent.parent]:
        vf = p / "VERSION"
        if vf.exists():
            return vf.read_text().strip()
    return ""


def _fetch_remote_version() -> str:
    """Fetch the VERSION file from GitHub's raw content API."""
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{VERSION_PATH}"
    req = urllib.request.Request(url, headers={"User-Agent": "fhir-jira-toolkit-update-check"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8").strip()


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a semver string into a comparable tuple."""
    parts = []
    for segment in v.split("."):
        # Strip pre-release suffixes
        num = segment.split("-")[0]
        try:
            parts.append(int(num))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def main() -> None:
    try:
        local = _read_local_version()
        if not local:
            return  # No VERSION file — can't compare

        remote = _fetch_remote_version()
        if not remote:
            return

        if _parse_version(remote) > _parse_version(local):
            envelope = {
                "hookResponse": {
                    "systemMessage": (
                        f"fhir-jira-toolkit update available: {local} \u2192 {remote}. "
                        f"Re-run `/plugin marketplace add jdlnolen/fhir-jira-toolkit` to update."
                    )
                }
            }
            print(json.dumps(envelope))
    except Exception:
        # Never block session start — fail silently on any error
        pass


if __name__ == "__main__":
    main()
