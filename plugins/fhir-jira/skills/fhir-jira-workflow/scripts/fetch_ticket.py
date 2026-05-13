#!/usr/bin/env python3
"""
Fetch HL7 FHIR JIRA tickets from the public browse URL.

HL7's JIRA at https://jira.hl7.org/ exposes individual ticket browse pages
without authentication. This script fetches the rendered HTML and extracts
the fields we need into a normalized JSON shape.

Note: this is intentionally NOT the JIRA REST API. The REST API at
/rest/api/2/issue/<KEY> requires authentication on HL7's instance. The
browse URL at /browse/<KEY> does not. Filters are similar — the public
XML export of a saved filter works without auth.

Usage:
    fetch_ticket.py FHIR-12345
    fetch_ticket.py FHIR-12345 FHIR-12346 FHIR-12347
    fetch_ticket.py --filter 24101
    fetch_ticket.py FHIR-12345 --cache-dir /tmp/staging
    fetch_ticket.py FHIR-12345 --dump-html   # save raw HTML for debugging

Output format (cached at <cache-dir>/<KEY>.json):
    {
      "key": "FHIR-12345",
      "url": "https://jira.hl7.org/browse/FHIR-12345",
      "summary": "...",
      "status": "Closed",
      "resolution": "Persuasive with Modification",
      "issuetype": "Change Request",
      "description": "...body text...",
      "fields": {
        "Specification": "FHIR Core (FHIR)",
        "Related URL": "https://hl7.org/fhir/observation.html",
        "Resolution Description": "...",
        ...
      },
      "fetched_at": "2026-05-12T16:00:00Z"
    }
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

JIRA_BASE = "https://jira.hl7.org"
DEFAULT_CACHE_DIR = Path(".jira-cache")
USER_AGENT = "Mozilla/5.0 (compatible; fhir-jira-toolkit/0.2)"
_TICKET_KEY_RE = re.compile(r"^[A-Z]+-\d+$")
_FILTER_ID_RE = re.compile(r"^\d+$")


def _http_get(url: str, timeout: int = 30) -> str:
    """Fetch a URL with a browser-like User-Agent. Returns the response body as text."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------


class _IssuePageExtractor(HTMLParser):
    """
    Walks the issue browse-page DOM and extracts:
      - Core fields by element id (summary-val, status-val, etc.)
      - Custom fields by pairing <strong class="name">Label:</strong>
        with the value element that follows (id ends in '-val' or has
        class 'value')

    Description is captured separately.

    Implementation: tracks document depth. Each active capture remembers
    the depth at which it started, and closes when an end tag drops us
    back to that depth.
    """

    CORE_IDS = {
        "summary-val": "summary",
        "status-val": "status",
        "resolution-val": "resolution",
        "type-val": "issuetype",
        "priority-val": "priority",
    }

    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth = 0

        # Each active capture: (started_at_depth, buffer_list)
        self._core: dict[str, tuple[int, list[str]]] = {}
        self._label: tuple[int, list[str]] | None = None
        self._value: tuple[int, list[str]] | None = None
        self._desc: tuple[int, list[str]] | None = None

        self._pending_label: str | None = None

        # Outputs
        self.core: dict[str, str] = {}
        self.fields: dict[str, str] = {}
        self.description_text: str = ""
        self.description_links: list[str] = []

    @staticmethod
    def _attrs_dict(attrs):
        return {k: v for (k, v) in attrs if v is not None}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.VOID_ELEMENTS:
            # Capture description links even on void elements? No, hrefs are on <a> which isn't void.
            return

        self._depth += 1
        a = self._attrs_dict(attrs)
        tid = a.get("id", "") or ""
        cls = (a.get("class", "") or "").split()

        # Core capture
        if tid in self.CORE_IDS:
            key = self.CORE_IDS[tid]
            if key not in self._core:
                self._core[key] = (self._depth, [])

        # Description capture
        if self._desc is None and (
            tid == "description-val"
            or (tag == "div" and "user-content-block" in cls)
        ):
            self._desc = (self._depth, [])

        # Inside description: record link hrefs
        if self._desc is not None and tag == "a":
            href = a.get("href", "")
            if href.startswith("http"):
                self.description_links.append(href)

        # Custom-field label
        if tag == "strong" and "name" in cls and self._label is None:
            self._label = (self._depth, [])

        # Custom-field value (only when we have a pending label to pair it with)
        if self._pending_label and self._value is None:
            is_val_id = tid.endswith("-val") and tid not in self.CORE_IDS
            is_value_cls = "value" in cls
            if is_val_id or is_value_cls:
                self._value = (self._depth, [])

        # Inside a value: capture link hrefs as literal text
        if self._value is not None and tag == "a":
            href = a.get("href", "")
            if href.startswith("http"):
                _d, buf = self._value
                buf.append(f" {href} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_ELEMENTS:
            return

        # Close any captures whose start depth matches the current depth
        for key in list(self._core.keys()):
            d, buf = self._core[key]
            if d == self._depth:
                text = " ".join(s.strip() for s in buf if s.strip())
                if text and key not in self.core:
                    self.core[key] = text
                del self._core[key]

        if self._label is not None and self._label[0] == self._depth:
            _d, buf = self._label
            label = " ".join(s.strip() for s in buf if s.strip()).rstrip(":").strip()
            if label:
                self._pending_label = label
            self._label = None

        if self._value is not None and self._value[0] == self._depth:
            _d, buf = self._value
            value = " ".join(s.strip() for s in buf if s.strip())
            if self._pending_label and value:
                self.fields[self._pending_label] = value
                self._pending_label = None
            # If value was empty, keep _pending_label alive for the next value element
            self._value = None

        if self._desc is not None and self._desc[0] == self._depth:
            _d, buf = self._desc
            self.description_text = " ".join(s.strip() for s in buf if s.strip())
            self._desc = None

        self._depth -= 1

    def handle_data(self, data: str) -> None:
        # Route to whichever captures are active
        for _key, (_d, buf) in self._core.items():
            buf.append(data)
        if self._label is not None:
            self._label[1].append(data)
        if self._value is not None:
            self._value[1].append(data)
        if self._desc is not None:
            self._desc[1].append(data)


def _fallback_regex_extract(html_text: str) -> dict[str, str]:
    """
    Simpler regex-based fallback that finds the major fields.

    Used to fill in anything the HTML parser missed. Patterns target
    the common Jira Server DOM:

      <h1 id="summary-val" ...>Summary text</h1>
      <span id="status-val"><span ...>Closed</span></span>
      <span id="resolution-val">Persuasive</span>
    """
    out: dict[str, str] = {}

    def first_match(pattern: str, flags=re.S) -> str:
        m = re.search(pattern, html_text, flags)
        if not m:
            return ""
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        text = html.unescape(text)
        return " ".join(text.split()).strip()

    out["summary"] = first_match(r'<h1[^>]*id="summary-val"[^>]*>(.*?)</h1>')
    out["status"] = first_match(r'<span[^>]*id="status-val"[^>]*>(.*?)</span>\s*</span>')
    if not out["status"]:
        out["status"] = first_match(r'id="status-val"[^>]*>(.*?)</span>')
    out["resolution"] = first_match(r'id="resolution-val"[^>]*>(.*?)</span>')
    out["issuetype"] = first_match(r'id="type-val"[^>]*>(.*?)</span>')
    return {k: v for k, v in out.items() if v}


def parse_issue_html(key: str, html_text: str) -> dict[str, Any]:
    parser = _IssuePageExtractor()
    parser.feed(html_text)
    parser.close()

    core = dict(parser.core)
    # Apply regex fallback for any missing core fields
    fallback = _fallback_regex_extract(html_text)
    for k, v in fallback.items():
        if k not in core or not core[k]:
            core[k] = v

    fields = dict(parser.fields)

    # Stash description URLs as a synthetic hint for repo resolution
    if parser.description_links and "Related URL" not in fields:
        fields["_description_links"] = ", ".join(parser.description_links[:5])

    return {
        "key": key,
        "url": f"{JIRA_BASE}/browse/{key}",
        "summary": core.get("summary", ""),
        "status": core.get("status", ""),
        "resolution": core.get("resolution") or "(unresolved)",
        "issuetype": core.get("issuetype", ""),
        "description": parser.description_text,
        "fields": fields,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def fetch_issue(key: str, dump_html_dir: Path | None = None) -> dict[str, Any]:
    if not _TICKET_KEY_RE.fullmatch(key):
        raise ValueError(f"Invalid ticket key format: {key!r} (expected PROJECT-NUMBER, e.g. FHIR-12345)")
    url = f"{JIRA_BASE}/browse/{urllib.parse.quote(key)}"
    body = _http_get(url)
    if dump_html_dir is not None:
        dump_html_dir.mkdir(parents=True, exist_ok=True)
        (dump_html_dir / f"{key}.html").write_text(body)
    return parse_issue_html(key, body)


# ---------------------------------------------------------------------------
# Filter resolution via the public XML export endpoint
# ---------------------------------------------------------------------------


def fetch_filter_keys(filter_id: str) -> list[str]:
    """
    Resolve a saved JIRA filter to its ticket-key list via the public
    XML view endpoint:

        /sr/jira.issueviews:searchrequest-xml/<id>/SearchRequest-<id>.xml?tempMax=1000

    For public filters this works without authentication.
    """
    if not _FILTER_ID_RE.fullmatch(filter_id):
        raise ValueError(f"Invalid filter ID format: {filter_id!r} (expected numeric ID, e.g. 24101)")
    url = (
        f"{JIRA_BASE}/sr/jira.issueviews:searchrequest-xml/"
        f"{urllib.parse.quote(filter_id)}/SearchRequest-{urllib.parse.quote(filter_id)}.xml"
        f"?tempMax=1000"
    )
    body = _http_get(url)
    keys = re.findall(r"<key[^>]*>([A-Z]+-\d+)</key>", body)
    return sorted(set(keys))


# ---------------------------------------------------------------------------
# Display + cache
# ---------------------------------------------------------------------------


def normalized_summary(issue: dict[str, Any]) -> str:
    out: list[str] = []
    out.append(f"=== {issue['key']} ===")
    out.append(f"Summary    : {issue.get('summary', '')}")
    out.append(f"Status     : {issue.get('status', '')}")
    out.append(f"Resolution : {issue.get('resolution', '')}")
    if issue.get("issuetype"):
        out.append(f"Type       : {issue['issuetype']}")
    for name, value in (issue.get("fields") or {}).items():
        if name.startswith("_"):
            continue
        out.append(f"{name:11}: {value}")
    if issue.get("description"):
        out.append("")
        out.append("--- Description ---")
        out.append(issue["description"])
    return "\n".join(out)


def cache_issue(issue: dict[str, Any], cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{issue['key']}.json"
    path.write_text(json.dumps(issue, indent=2))
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keys", nargs="*", help="Ticket keys, e.g. FHIR-12345")
    parser.add_argument("--filter", help="JIRA filter ID to resolve to a ticket list")
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help=f"Where to cache ticket JSONs (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--dump-html",
        action="store_true",
        help="Save raw HTML for each ticket alongside the JSON (for debugging extraction)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress normalized summary output")
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir).expanduser()
    keys: list[str] = list(args.keys)

    if args.filter:
        try:
            filter_keys = fetch_filter_keys(args.filter)
        except urllib.error.HTTPError as e:
            print(
                f"Error fetching filter {args.filter}: HTTP {e.code}\n"
                f"  URL: {e.url}\n"
                f"  Note: private filters require authentication. If this filter\n"
                f"  is private, pass ticket keys explicitly instead.",
                file=sys.stderr,
            )
            return 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            print(f"Error fetching filter {args.filter}: {e}", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"# Filter {args.filter} resolved to {len(filter_keys)} ticket(s):")
            for k in filter_keys:
                print(k)
        keys.extend(filter_keys)

    if not keys:
        parser.print_help()
        return 2

    dump_dir = cache_dir / "_html-dumps" if args.dump_html else None
    rc = 0
    for key in keys:
        try:
            issue = fetch_issue(key, dump_html_dir=dump_dir)
            cache_path = cache_issue(issue, cache_dir)
            if not args.quiet:
                print()
                print(normalized_summary(issue))
                print(f"\n[cached: {cache_path}]")
        except urllib.error.HTTPError as e:
            print(f"Error fetching {key}: HTTP {e.code} ({e.reason})", file=sys.stderr)
            rc = 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            print(f"Error fetching {key}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
