#!/usr/bin/env python3
"""
Resolve which FHIR repository a JIRA ticket targets.

Reads the cached ticket JSON, looks up the target spec via the repo map
(default + optional user override), and prints the resolved repo metadata.

Usage:
    resolve_repo.py --ticket .jira-cache/FHIR-12345.json
    resolve_repo.py --ticket .jira-cache/FHIR-12345.json --json
    resolve_repo.py --list
    resolve_repo.py --group .jira-cache/FHIR-1.json,.jira-cache/FHIR-2.json
        # Outputs JSON: {"HL7/fhir": ["FHIR-1"], "HL7/US-Core": ["FHIR-2"]}

Resolution order:
    1. Match the ticket's "Specification" custom field against
       specifications[*].names (case-insensitive substring match).
    2. Fall back to matching the ticket's "Related URL" against
       specifications[*].url_patterns (regex).
    3. If still ambiguous, exit 2 and surface the candidates.

Repo map locations (later wins for duplicate GitHub slugs):
    1. <plugin-root>/skills/fhir-jira-workflow/repo-map.json (shipped)
    2. ~/.config/fhir-jira-toolkit/repo-map.json (user override)
    3. ./repo-map.local.json (project-local override)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


SHIPPED_MAP_REL = "skills/fhir-jira-workflow/repo-map.json"
USER_MAP = Path.home() / ".config" / "fhir-jira-toolkit" / "repo-map.json"
# Intentionally CWD-relative: project-local override for the repo the user is working in
PROJECT_MAP = Path("repo-map.local.json")


def _plugin_root() -> Path:
    """Locate the plugin root.

    Priority:
      1. $FHIR_JIRA_PLUGIN_ROOT (explicit cross-host override)
      2. $PLUGIN_ROOT (set by Codex)
      3. $CLAUDE_PLUGIN_ROOT (set by Claude Code and by Codex for compatibility)
      4. Walk up from this file looking for either host's plugin manifest
    """
    for env_name in ("FHIR_JIRA_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(env_name)
        if value:
            return Path(value)
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if any(
            (p / host_dir / "plugin.json").exists()
            for host_dir in (".codex-plugin", ".claude-plugin")
        ):
            return p
    return here.parent.parent.parent.parent  # best effort


def load_map() -> dict[str, Any]:
    """Load and merge repo maps."""
    plugin_root = _plugin_root()
    shipped = plugin_root / SHIPPED_MAP_REL

    base: dict[str, Any] = {}
    if shipped.exists():
        base = json.loads(shipped.read_text())
    else:
        # Fallback: assume we're being run from inside the skill dir
        local = Path(__file__).resolve().parent.parent / "repo-map.json"
        if local.exists():
            base = json.loads(local.read_text())
        else:
            raise FileNotFoundError(f"Could not locate repo-map.json (looked at {shipped})")

    for override_path in (USER_MAP, PROJECT_MAP):
        if override_path.exists():
            try:
                override = json.loads(override_path.read_text())
            except Exception as e:
                print(
                    f"Warning: skipping malformed override {override_path}: {e}",
                    file=sys.stderr,
                )
                continue
            base = _merge_maps(base, override)

    return base


def _merge_maps(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Merge override on top of base. Match by GitHub slug; later wins."""
    merged = dict(base)
    if "default_clone_root" in over:
        merged["default_clone_root"] = over["default_clone_root"]
    base_specs = list(base.get("specifications", []))
    over_specs = list(over.get("specifications", []))
    by_slug: dict[str, dict[str, Any]] = {}
    for spec in base_specs + over_specs:
        slug = spec.get("github", "")
        if not slug:
            continue
        existing = dict(by_slug.get(slug, {}))
        for k, v in spec.items():
            if k in ("names", "url_patterns") and k in existing and isinstance(v, list):
                # Extend list fields rather than replacing them
                seen = set(existing[k])
                existing[k] = existing[k] + [x for x in v if x not in seen]
            else:
                existing[k] = v
        by_slug[slug] = existing
    merged["specifications"] = list(by_slug.values())
    return merged


def _expand_path(s: str | None) -> Path | None:
    if not s:
        return None
    s = os.path.expandvars(os.path.expanduser(s))
    return Path(s)


def resolve_local_path(spec: dict[str, Any], default_clone_root: str | None) -> Path:
    """Determine the local clone path for a spec entry."""
    explicit = _expand_path(spec.get("local_path"))
    if explicit:
        return explicit
    root = _expand_path(default_clone_root) or Path.home() / "dev" / "hl7"
    repo_name = spec["github"].split("/")[-1]
    return root / repo_name


def _ticket_field(ticket: dict[str, Any], display_name: str) -> Any:
    """Look up a field from the cached ticket.

    Supports the cached ticket shape produced by fetch_ticket.py:
        {"fields": {"Specification": "...", "Related URL": "..."}}
    """
    fields = ticket.get("fields", {})
    if not isinstance(fields, dict):
        return None
    # Exact match
    if display_name in fields:
        return fields[display_name]
    # Case-insensitive fallback
    low = display_name.lower()
    for k, v in fields.items():
        if k.lower() == low:
            return v
    return None


def _normalize_spec_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("value") or val.get("name") or "")
    if isinstance(val, list):
        parts = [_normalize_spec_value(v) for v in val]
        return " ".join(p for p in parts if p)
    return str(val)


def _candidate_urls(ticket: dict[str, Any]) -> list[str]:
    """Pull URLs from Related URL fields, description, and _description_links hint."""
    urls: list[str] = []
    for fname in ("Related URL", "Related URLs", "_description_links"):
        v = _ticket_field(ticket, fname)
        if v:
            urls.extend(re.findall(r"https?://\S+", str(v)))
    desc = ticket.get("description", "")
    if desc:
        urls.extend(re.findall(r"https?://[^\s)\]>\"']+", str(desc)))
    return urls


def resolve_for_ticket(
    ticket: dict[str, Any], repo_map: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    """Return (matching spec entry, reason) or (None, reason).

    Matching is bidirectional substring (case-insensitive) over names.
    When multiple specs match (a generic alias like "Core" might match
    both "FHIR Core" and "US Core"), the spec whose longest matching name
    is longest wins — most-specific match.
    """
    specs = repo_map.get("specifications", [])
    spec_value = _normalize_spec_value(_ticket_field(ticket, "Specification"))

    if spec_value:
        sv_low = spec_value.lower()
        # Track (spec, longest_matching_name_length, matching_name)
        candidates: list[tuple[dict[str, Any], int, str]] = []
        for spec in specs:
            best_for_spec = 0
            best_name = ""
            for name in spec.get("names", []):
                nl = name.lower()
                if nl in sv_low:
                    overlap = len(nl)
                elif sv_low in nl:
                    overlap = len(sv_low)
                else:
                    continue
                if overlap > best_for_spec:
                    best_for_spec = overlap
                    best_name = name
            if best_for_spec > 0:
                candidates.append((spec, best_for_spec, best_name))

        if len(candidates) == 1:
            spec, _score, name = candidates[0]
            return spec, f"matched Specification field {spec_value!r} via name {name!r}"

        if len(candidates) > 1:
            # Longest-match tie-breaker
            candidates.sort(key=lambda t: t[1], reverse=True)
            top_score = candidates[0][1]
            top = [c for c in candidates if c[1] == top_score]
            if len(top) == 1:
                spec, _score, name = top[0]
                return spec, (
                    f"matched Specification field {spec_value!r} via name {name!r} "
                    f"(longest match; also matched: "
                    f"{', '.join(c[0].get('github', '?') for c in candidates[1:])})"
                )
            slugs = ", ".join(c[0].get("github", "?") for c in top)
            return None, (
                f"ambiguous Specification value {spec_value!r} — "
                f"top matches tied: {slugs}. Add a more specific name pattern to repo-map.json."
            )

    urls = _candidate_urls(ticket)
    url_matches: list[tuple[dict[str, Any], str]] = []
    for spec in specs:
        for pattern in spec.get("url_patterns", []) or []:
            if any(re.search(pattern, u) for u in urls):
                url_matches.append((spec, pattern))
                break  # one match per spec is enough
    if len(url_matches) == 1:
        spec, pattern = url_matches[0]
        return spec, f"matched URL pattern {pattern!r}"
    if len(url_matches) > 1:
        slugs = ", ".join(m[0].get("github", "?") for m in url_matches)
        return None, (
            f"ambiguous URL pattern match — multiple specs matched: {slugs}. "
            f"Add a Specification field or refine url_patterns in repo-map.json."
        )

    return None, (
        "no Specification field match and no URL pattern match. "
        f"Specification={spec_value!r}, URLs={urls[:3]}"
    )


def render_human(spec: dict[str, Any], local_path: Path) -> str:
    lines = [
        f"GitHub        : {spec['github']}",
        f"Local path    : {local_path}",
        f"Local exists  : {'yes' if local_path.exists() else 'NO — clone or set local_path'}",
        f"Default branch: {spec.get('default_branch', '(detect via git)')}",
        f"Publisher     : {spec.get('publisher', '(detect)')}",
        f"QA path       : {spec.get('qa_path', 'output/qa.json')}",
        f"Build dirs    : {', '.join(spec.get('build_dirs', ['output', 'temp']))}",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", help="Path to cached ticket JSON")
    parser.add_argument(
        "--group",
        help="Comma-separated paths to cached ticket JSONs; output JSON of {github_slug: [keys]}",
    )
    parser.add_argument("--list", action="store_true", help="List all known specifications")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text")
    args = parser.parse_args(argv)

    repo_map = load_map()
    default_root = repo_map.get("default_clone_root")

    if args.list:
        out = []
        for spec in repo_map.get("specifications", []):
            entry = {
                "github": spec["github"],
                "names": spec.get("names", []),
                "default_branch": spec.get("default_branch"),
                "publisher": spec.get("publisher"),
                "qa_path": spec.get("qa_path", "output/qa.json"),
                "build_dirs": spec.get("build_dirs", ["output", "temp"]),
                "local_path": str(resolve_local_path(spec, default_root)),
            }
            out.append(entry)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            for e in out:
                print(f"- {e['github']}  ({', '.join(e['names'])})")
                print(f"    local: {e['local_path']}")
                print(f"    branch: {e['default_branch']}  publisher: {e['publisher']}")
                print(f"    qa_path: {e['qa_path']}  build_dirs: {', '.join(e['build_dirs'])}")
        return 0

    if args.group:
        paths = [p.strip() for p in args.group.split(",") if p.strip()]
        groups: dict[str, list[str]] = {}
        unresolved: list[dict[str, str]] = []
        for p in paths:
            try:
                ticket = json.loads(Path(p).read_text())
            except (OSError, json.JSONDecodeError) as e:
                unresolved.append({"key": p, "reason": f"failed to read ticket file: {e}"})
                continue
            spec, reason = resolve_for_ticket(ticket, repo_map)
            key = ticket.get("key", p)
            if spec is None:
                unresolved.append({"key": key, "reason": reason})
            else:
                groups.setdefault(spec["github"], []).append(key)
        result = {"groups": groups, "unresolved": unresolved}
        print(json.dumps(result, indent=2))
        return 0 if not unresolved else 3

    if not args.ticket:
        parser.error("one of --ticket, --group, or --list is required")

    ticket = json.loads(Path(args.ticket).read_text())
    spec, reason = resolve_for_ticket(ticket, repo_map)
    if spec is None:
        print(f"UNRESOLVED: {reason}", file=sys.stderr)
        return 2

    local_path = resolve_local_path(spec, default_root)

    if args.json:
        out = {
            "github": spec["github"],
            "local_path": str(local_path),
            "local_exists": local_path.exists(),
            "default_branch": spec.get("default_branch"),
            "publisher": spec.get("publisher"),
            "qa_path": spec.get("qa_path", "output/qa.json"),
            "build_dirs": spec.get("build_dirs", ["output", "temp"]),
            "names": spec.get("names", []),
            "match_reason": reason,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"# {reason}")
        print(render_human(spec, local_path))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
