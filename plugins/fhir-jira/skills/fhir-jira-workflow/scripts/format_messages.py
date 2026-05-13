#!/usr/bin/env python3
"""
Format commit messages and PR bodies for FHIR JIRA tickets.

Single ticket:
    format_messages.py \\
        --ticket .jira-cache/FHIR-12345.json \\
        --synopsis-file path/to/synopsis.txt \\
        --files-changed "$(git diff --name-only --cached)" \\
        --qa-delta .jira-cache/qa-delta.json \\
        --out-commit .jira-cache/FHIR-12345.commit.txt \\
        --out-pr .jira-cache/FHIR-12345.pr.md

Batch:
    format_messages.py --batch \\
        --tickets FHIR-1234,FHIR-1235,FHIR-1236 \\
        --synopses-file .jira-cache/batch-synopses.json \\
        --qa-delta .jira-cache/qa-delta.json \\
        --out-pr .jira-cache/batch.pr.md

batch-synopses.json structure:
    {
      "FHIR-1234": {
        "summary": "Short summary from ticket",
        "synopsis": "What was actually done",
        "files": ["source/foo/foo.xml", "source/foo/foo-notes.md"],
        "disposition": "Persuasive"
      },
      ...
    }
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

JIRA_BROWSE = "https://jira.hl7.org/browse"
SUBJECT_LIMIT = 72
BODY_WRAP = 72


def load_ticket(path: Path) -> dict[str, Any]:
    """Load a cached ticket (fetch_ticket.py output format)."""
    raw = json.loads(path.read_text())
    custom_fields = raw.get("fields", {}) or {}

    def by_name(name: str) -> str:
        # Exact, then case-insensitive
        if name in custom_fields:
            return str(custom_fields[name])
        low = name.lower()
        for k, v in custom_fields.items():
            if k.lower() == low:
                return str(v)
        return ""

    resolution = (raw.get("resolution") or "(unresolved)").strip()

    disposition = (
        by_name("Resolution Description")
        or by_name("Resolution Notes")
        or raw.get("description")
        or ""
    )

    key = raw.get("key", "")
    return {
        "key": key,
        "summary": (raw.get("summary") or "").strip(),
        "resolution": resolution,
        "disposition": str(disposition).strip(),
        "url": raw.get("url") or f"{JIRA_BROWSE}/{key}",
    }


def truncate_subject(text: str, key: str, limit: int = SUBJECT_LIMIT) -> str:
    prefix = f"{key}: "
    room = limit - len(prefix)
    if room <= 0:
        return prefix.strip()
    if len(text) <= room:
        return prefix + text
    return prefix + text[: room - 1].rstrip() + "\u2026"


def wrap_body(text: str, width: int = BODY_WRAP) -> str:
    paragraphs = text.split("\n\n")
    out = []
    for p in paragraphs:
        # Don't reflow lines that look like blockquotes or lists
        if any(p.lstrip().startswith(prefix) for prefix in ("> ", "- ", "* ", "  ")):
            out.append(p)
        else:
            out.append("\n".join(textwrap.wrap(p, width=width) or [""]))
    return "\n\n".join(out)


def format_commit(ticket: dict[str, Any], synopsis: str) -> str:
    subject = truncate_subject(ticket["summary"], ticket["key"])
    body = wrap_body(synopsis.strip())
    parts = [
        subject,
        "",
        body,
        "",
        f"Disposition: {ticket['resolution']}",
        f"Ticket: {ticket['url']}",
    ]
    return "\n".join(parts) + "\n"


def format_pr_single(
    ticket: dict[str, Any],
    synopsis: str,
    files: list[str],
    qa_delta: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    parts.append(
        f"Resolves [{ticket['key']}]({ticket['url']}): {ticket['summary']}"
    )
    parts.append("")
    parts.append("## What changed")
    parts.append(synopsis.strip())
    parts.append("")

    if files:
        parts.append("## Files touched")
        for f in files:
            parts.append(f"- `{f}`")
        parts.append("")

    if qa_delta:
        parts.append(_format_qa_section(qa_delta))

    return "\n".join(parts).rstrip() + "\n"


def format_pr_batch(
    tickets: list[dict[str, Any]],
    synopses: dict[str, dict[str, Any]],
    qa_delta: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    parts.append(f"This PR addresses {len(tickets)} ticket(s).")
    parts.append("")
    parts.append("## Tickets")
    for t in tickets:
        parts.append(f"- [{t['key']}]({t['url']}): {t['summary']}")
    parts.append("")

    for t in tickets:
        entry = synopses.get(t["key"], {})
        parts.append(f"## {t['key']}: {t['summary']}")
        parts.append("")
        synopsis = entry.get("synopsis") or "_(no synopsis recorded)_"
        parts.append(synopsis.strip())
        parts.append("")
        files = entry.get("files") or []
        if files:
            parts.append("**Files:** " + ", ".join(f"`{f}`" for f in files))
            parts.append("")
        parts.append(f"[Ticket]({t['url']})")
        parts.append("")
        parts.append("---")
        parts.append("")

    if qa_delta:
        parts.append(_format_qa_section(qa_delta))

    return "\n".join(parts).rstrip() + "\n"


def _format_qa_section(qa: dict[str, Any]) -> str:
    lines = ["## Publisher QA"]
    cur = qa.get("current", {})
    base = qa.get("baseline")
    d = qa.get("delta", {})
    if base is None:
        lines.append("")
        for k, v in cur.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("")
        lines.append("| metric | baseline | current | delta |")
        lines.append("|---|---:|---:|---:|")
        for k in cur:
            dv = d.get(k)
            sign = "+" if isinstance(dv, int) and dv > 0 else ""
            lines.append(f"| {k} | {base.get(k, 0)} | {cur[k]} | {sign}{dv} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="store_true")

    # single
    parser.add_argument("--ticket", help="Path to cached ticket JSON")
    parser.add_argument("--synopsis-file", help="Path to synopsis text")
    parser.add_argument("--files-changed", default="", help="Newline or whitespace separated file list")
    parser.add_argument("--out-commit", help="Output path for commit message")

    # batch
    parser.add_argument("--tickets", help="Comma-separated ticket keys (batch mode)")
    parser.add_argument("--synopses-file", help="JSON map of synopses (batch mode)")
    parser.add_argument("--cache-dir", default=".jira-cache", help="Where ticket JSONs are cached")

    # both
    parser.add_argument("--qa-delta", help="Path to qa-delta.json from parse_qa.py")
    parser.add_argument("--out-pr", required=True, help="Output path for PR body markdown")

    args = parser.parse_args(argv)

    qa_delta = None
    if args.qa_delta and Path(args.qa_delta).exists():
        qa_delta = json.loads(Path(args.qa_delta).read_text())

    Path(args.out_pr).parent.mkdir(parents=True, exist_ok=True)

    if args.batch:
        if not args.tickets or not args.synopses_file:
            print("--batch requires --tickets and --synopses-file", file=sys.stderr)
            return 2
        keys = [k.strip() for k in args.tickets.split(",") if k.strip()]
        cache_dir = Path(args.cache_dir)
        tickets = [load_ticket(cache_dir / f"{k}.json") for k in keys]
        synopses = json.loads(Path(args.synopses_file).read_text())
        pr = format_pr_batch(tickets, synopses, qa_delta)
        Path(args.out_pr).write_text(pr)
        print(f"Wrote PR body: {args.out_pr}")
        return 0

    # single mode
    if not args.ticket or not args.synopsis_file or not args.out_commit:
        print(
            "single-ticket mode requires --ticket, --synopsis-file, --out-commit",
            file=sys.stderr,
        )
        return 2

    ticket = load_ticket(Path(args.ticket))
    synopsis = Path(args.synopsis_file).read_text().strip()

    files = [f.strip() for f in args.files_changed.replace("\n", " ").split() if f.strip()]

    commit = format_commit(ticket, synopsis)
    Path(args.out_commit).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_commit).write_text(commit)
    print(f"Wrote commit message: {args.out_commit}")

    pr = format_pr_single(ticket, synopsis, files, qa_delta)
    Path(args.out_pr).write_text(pr)
    print(f"Wrote PR body: {args.out_pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
