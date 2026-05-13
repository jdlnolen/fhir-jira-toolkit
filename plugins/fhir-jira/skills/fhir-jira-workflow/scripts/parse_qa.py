#!/usr/bin/env python3
"""
Parse the IG Publisher's qa.json and compute a delta against a baseline.

The IG Publisher writes output/qa.json with summary counts of errors, warnings,
information messages, and broken links, plus a per-file breakdown of issues.

Usage:
    parse_qa.py --current output/qa.json
    parse_qa.py --current output/qa.json --baseline .jira-cache/qa-baseline.json
    parse_qa.py --current output/qa.json --baseline .jira-cache/qa-baseline.json \\
                --out .jira-cache/qa-delta.json

Exit codes:
    0   QA is good (errors did not increase)
    1   QA regressed (errors increased)
    2   Invalid input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_qa(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"qa file not found: {path}")
    return json.loads(path.read_text())


def _to_int(v: Any, default: int = 0) -> int:
    """Safely coerce a value to int, returning default on failure."""
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def counts(qa: dict[str, Any]) -> dict[str, int]:
    """
    Extract summary counts. The IG Publisher's qa.json schema has varied
    across versions, so we look in several places:
      - Top-level 'errs'/'warnings'/'hints'/'links' (newer)
      - Top-level 'errors'/'warnings' (older)
      - 'summary' nested object
      - Aggregated from per-file 'messages' arrays as fallback
    """
    out = {"errors": 0, "warnings": 0, "info": 0, "broken_links": 0}

    # Newer top-level keys
    if "errs" in qa:
        out["errors"] = _to_int(qa.get("errs"))
        out["warnings"] = _to_int(qa.get("warnings"))
        out["info"] = _to_int(qa.get("hints", qa.get("info", 0)))
        out["broken_links"] = _to_int(qa.get("links", qa.get("brokenlinks", 0)))
        return out

    # Older top-level keys
    if "errors" in qa or "warnings" in qa:
        out["errors"] = _to_int(qa.get("errors"))
        out["warnings"] = _to_int(qa.get("warnings"))
        out["info"] = _to_int(qa.get("info"))
        out["broken_links"] = _to_int(qa.get("brokenlinks", qa.get("links", 0)))
        return out

    # Summary subobject
    summary = qa.get("summary")
    if isinstance(summary, dict):
        out["errors"] = _to_int(summary.get("errors", summary.get("errs", 0)))
        out["warnings"] = _to_int(summary.get("warnings"))
        out["info"] = _to_int(summary.get("info", summary.get("hints", 0)))
        out["broken_links"] = _to_int(
            summary.get("brokenlinks", summary.get("links", 0))
        )
        return out

    # Fallback: walk per-file messages
    found_any = False
    for entry in qa.get("files", []) or []:
        for msg in entry.get("messages", []) or []:
            found_any = True
            level = (msg.get("level") or msg.get("severity") or "").lower()
            if level in ("error", "fatal"):
                out["errors"] += 1
            elif level == "warning":
                out["warnings"] += 1
            elif level in ("information", "info", "hint"):
                out["info"] += 1
            elif level in ("broken-link", "brokenlink"):
                out["broken_links"] += 1
    if not found_any and all(v == 0 for v in out.values()):
        print(
            "Warning: qa.json schema not recognized — no counts extracted. "
            "Regression check may report false-green.",
            file=sys.stderr,
        )
    return out


def delta(current: dict[str, int], baseline: dict[str, int] | None) -> dict[str, Any]:
    if baseline is None:
        return {
            "current": current,
            "baseline": None,
            "delta": {k: None for k in current},
            "regressed": False,
        }
    d = {k: current[k] - baseline.get(k, 0) for k in current}
    return {
        "current": current,
        "baseline": baseline,
        "delta": d,
        "regressed": d["errors"] > 0,
    }


def render(report: dict[str, Any]) -> str:
    cur = report["current"]
    base = report["baseline"]
    d = report["delta"]
    lines = []
    if base is None:
        lines.append("QA snapshot (no baseline):")
        for k, v in cur.items():
            lines.append(f"  {k:13} : {v}")
    else:
        lines.append("QA delta (current vs baseline):")
        lines.append(f"  {'metric':13} {'baseline':>10} {'current':>10} {'delta':>8}")
        for k in cur:
            sign = "+" if d[k] > 0 else ""
            lines.append(
                f"  {k:13} {base.get(k, 0):>10} {cur[k]:>10} {sign}{d[k]:>7}"
            )
        if report["regressed"]:
            lines.append("")
            lines.append("REGRESSED: error count increased. Do NOT commit.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", required=True, help="Path to current qa.json")
    parser.add_argument("--baseline", help="Path to baseline qa.json")
    parser.add_argument("--out", help="Path to write delta JSON")
    args = parser.parse_args(argv)

    try:
        cur = counts(load_qa(Path(args.current)))
    except Exception as e:
        print(f"Failed to read current qa.json: {e}", file=sys.stderr)
        return 2

    base: dict[str, int] | None = None
    if args.baseline:
        base_path = Path(args.baseline)
        if base_path.exists():
            try:
                base = counts(load_qa(base_path))
            except Exception as e:
                print(f"Warning: failed to read baseline ({e}); proceeding without it", file=sys.stderr)

    report = delta(cur, base)
    print(render(report))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))

    return 1 if report["regressed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
