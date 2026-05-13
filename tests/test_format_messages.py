"""Tests for format_messages.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import format_messages
from format_messages import (
    _escape_backticks,
    _escape_md_link_text,
    _format_qa_section,
    format_commit,
    format_pr_batch,
    format_pr_single,
    main,
    truncate_subject,
    wrap_body,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TICKET = {
    "key": "FHIR-99",
    "summary": "Fix the broken widget",
    "resolution": "Persuasive",
    "disposition": "Apply the patch as written.",
    "url": "https://jira.hl7.org/browse/FHIR-99",
}


def make_ticket_json(tmp_path: Path, key: str = "FHIR-99", **overrides) -> Path:
    """Write a minimal ticket JSON file and return its path."""
    data = {
        "key": key,
        "summary": overrides.get("summary", "Fix the broken widget"),
        "resolution": overrides.get("resolution", "Persuasive"),
        "description": overrides.get("description", "Some description."),
        "url": overrides.get("url", f"https://jira.hl7.org/browse/{key}"),
        "fields": overrides.get("fields", {}),
    }
    path = tmp_path / f"{key}.json"
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# truncate_subject
# ---------------------------------------------------------------------------


class TestTruncateSubject:
    def test_short_text_returned_in_full(self):
        """Returns full text when the result is under the 72-char limit."""
        key = "FHIR-1"
        text = "Short summary"
        result = truncate_subject(text, key)
        assert result == f"{key}: {text}"
        assert len(result) <= 72

    def test_long_text_truncated_with_ellipsis(self):
        """Truncates with the unicode ellipsis so the result is exactly 72 chars."""
        key = "FHIR-1"
        # "FHIR-1: " is 8 chars, leaving 64 for the body.
        # Provide a text that is too long to fit.
        text = "A" * 70
        result = truncate_subject(text, key)
        assert len(result) == 72
        assert result.endswith("\u2026")
        assert result.startswith(f"{key}: ")

    def test_edge_case_key_prefix_exceeds_limit(self):
        """When the key prefix alone exceeds the limit, returns the stripped prefix."""
        key = "X" * 80  # prefix "X"*80 + ": " is 82 chars, over the 72 limit
        text = "Some summary"
        result = truncate_subject(text, key, limit=72)
        # room <= 0, so returns prefix.strip()
        assert result == f"{key}:"

    def test_text_exactly_fits_room(self):
        """Text that exactly fills the remaining room is not truncated."""
        key = "FHIR-1"
        prefix_len = len(f"{key}: ")
        room = 72 - prefix_len  # 64
        text = "B" * room
        result = truncate_subject(text, key)
        assert result == f"{key}: {text}"
        assert not result.endswith("\u2026")


# ---------------------------------------------------------------------------
# wrap_body
# ---------------------------------------------------------------------------


class TestWrapBody:
    def test_normal_paragraph_wrapped_at_72(self):
        """A long plain paragraph is re-flowed to at most 72 chars per line."""
        long_para = " ".join(["word"] * 30)  # well over 72 chars
        result = wrap_body(long_para)
        for line in result.splitlines():
            assert len(line) <= 72

    def test_blockquote_paragraph_preserved(self):
        """A paragraph whose lines start with '> ' is left untouched."""
        para = "> This is a blockquote line that is very long and should not be reflowed at all by the wrapper"
        result = wrap_body(para)
        assert result == para

    def test_list_paragraph_preserved(self):
        """A paragraph containing a '- ' list line is preserved as-is."""
        para = "- item one\n- item two\n- item three, which is quite a long entry and would be wrapped otherwise"
        result = wrap_body(para)
        assert result == para

    def test_multi_paragraph_structure_preserved(self):
        """Blank-line-separated paragraphs are kept separate in the output."""
        para1 = "First paragraph with some content."
        para2 = "Second paragraph with other content."
        combined = f"{para1}\n\n{para2}"
        result = wrap_body(combined)
        assert "\n\n" in result
        sections = result.split("\n\n")
        assert len(sections) == 2
        assert para1 in sections[0]
        assert para2 in sections[1]

    def test_star_list_paragraph_preserved(self):
        """A paragraph containing a '* ' list line is preserved as-is."""
        para = "* item alpha\n* item beta\n* item gamma that is quite long and would otherwise be reflowed by textwrap"
        result = wrap_body(para)
        assert result == para


# ---------------------------------------------------------------------------
# _escape_backticks
# ---------------------------------------------------------------------------


class TestEscapeBackticks:
    def test_backticks_escaped(self):
        assert _escape_backticks("foo`bar`baz") == "foo\\`bar\\`baz"

    def test_no_backticks_unchanged(self):
        assert _escape_backticks("no ticks here") == "no ticks here"

    def test_only_backticks(self):
        assert _escape_backticks("``") == "\\`\\`"


# ---------------------------------------------------------------------------
# _escape_md_link_text
# ---------------------------------------------------------------------------


class TestEscapeMdLinkText:
    def test_closing_bracket_escaped(self):
        result = _escape_md_link_text("foo]bar")
        assert result == "foo\\]bar"

    def test_closing_paren_escaped(self):
        result = _escape_md_link_text("foo)bar")
        assert result == "foo\\)bar"

    def test_both_characters_escaped(self):
        result = _escape_md_link_text("a]b)c")
        assert result == "a\\]b\\)c"

    def test_no_special_chars_unchanged(self):
        assert _escape_md_link_text("plain text") == "plain text"


# ---------------------------------------------------------------------------
# format_commit
# ---------------------------------------------------------------------------


class TestFormatCommit:
    def test_commit_structure(self):
        """Commit message has subject, blank line, body, blank line, trailers."""
        synopsis = "Updated the widget implementation."
        result = format_commit(TICKET, synopsis)
        lines = result.splitlines()

        # Subject is first line
        assert lines[0].startswith("FHIR-99: ")
        # Blank line separates subject from body
        assert lines[1] == ""
        # Body text is present
        assert synopsis in result
        # Trailers are present
        assert f"Disposition: {TICKET['resolution']}" in result
        assert f"Ticket: {TICKET['url']}" in result
        # File ends with newline
        assert result.endswith("\n")

    def test_commit_blank_line_before_trailers(self):
        """There is a blank line immediately before the trailers block."""
        synopsis = "Did a thing."
        result = format_commit(TICKET, synopsis)
        lines = result.rstrip("\n").splitlines()
        # Find the Disposition trailer line
        disp_idx = next(i for i, l in enumerate(lines) if l.startswith("Disposition:"))
        assert lines[disp_idx - 1] == ""


# ---------------------------------------------------------------------------
# format_pr_single
# ---------------------------------------------------------------------------


class TestFormatPrSingle:
    def test_contains_ticket_link(self):
        result = format_pr_single(TICKET, "Did a thing.", [], None)
        assert f"[{TICKET['key']}]({TICKET['url']})" in result

    def test_contains_synopsis(self):
        synopsis = "Implemented the new feature."
        result = format_pr_single(TICKET, synopsis, [], None)
        assert synopsis in result

    def test_contains_files_section(self):
        files = ["source/foo/foo.xml", "source/bar/bar.md"]
        result = format_pr_single(TICKET, "Synopsis.", files, None)
        assert "## Files touched" in result
        for f in files:
            assert f"`{f}`" in result

    def test_contains_qa_section(self):
        qa = {"current": {"errors": 2}, "baseline": {"errors": 3}, "delta": {"errors": -1}}
        result = format_pr_single(TICKET, "Synopsis.", [], qa)
        assert "## Publisher QA" in result

    def test_omits_qa_section_when_none(self):
        result = format_pr_single(TICKET, "Synopsis.", [], None)
        assert "## Publisher QA" not in result

    def test_summary_special_chars_escaped(self):
        ticket = dict(TICKET, summary="Fix thing] and (other)")
        result = format_pr_single(ticket, "Synopsis.", [], None)
        # The ] and ) in summary must be escaped inside link text
        assert "Fix thing\\] and (other\\)" in result

    def test_ends_with_newline(self):
        result = format_pr_single(TICKET, "Synopsis.", [], None)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# format_pr_batch
# ---------------------------------------------------------------------------


class TestFormatPrBatch:
    def _make_tickets(self):
        return [
            {
                "key": "FHIR-1",
                "summary": "First ticket",
                "resolution": "Persuasive",
                "disposition": "",
                "url": "https://jira.hl7.org/browse/FHIR-1",
            },
            {
                "key": "FHIR-2",
                "summary": "Second ticket",
                "resolution": "Not Persuasive",
                "disposition": "",
                "url": "https://jira.hl7.org/browse/FHIR-2",
            },
        ]

    def _make_synopses(self):
        return {
            "FHIR-1": {"synopsis": "Did the first thing.", "files": ["a.xml"]},
            "FHIR-2": {"synopsis": "Did the second thing.", "files": ["b.xml"]},
        }

    def test_contains_per_ticket_sections(self):
        tickets = self._make_tickets()
        synopses = self._make_synopses()
        result = format_pr_batch(tickets, synopses, None)
        assert "## FHIR-1: First ticket" in result
        assert "## FHIR-2: Second ticket" in result

    def test_contains_tickets_list(self):
        tickets = self._make_tickets()
        result = format_pr_batch(tickets, self._make_synopses(), None)
        assert "## Tickets" in result
        assert "[FHIR-1]" in result
        assert "[FHIR-2]" in result

    def test_contains_synopses_text(self):
        tickets = self._make_tickets()
        synopses = self._make_synopses()
        result = format_pr_batch(tickets, synopses, None)
        assert "Did the first thing." in result
        assert "Did the second thing." in result

    def test_fallback_when_no_synopsis(self):
        tickets = self._make_tickets()
        result = format_pr_batch(tickets, {}, None)
        assert "_(no synopsis recorded)_" in result

    def test_ends_with_newline(self):
        result = format_pr_batch(self._make_tickets(), self._make_synopses(), None)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# _format_qa_section
# ---------------------------------------------------------------------------


class TestFormatQaSection:
    def test_markdown_table_when_baseline_exists(self):
        qa = {
            "current": {"errors": 2, "warnings": 5},
            "baseline": {"errors": 3, "warnings": 5},
            "delta": {"errors": -1, "warnings": 0},
        }
        result = _format_qa_section(qa)
        assert "| metric | baseline | current | delta |" in result
        assert "|---|---:|---:|---:|" in result
        # Negative delta has no sign prefix
        assert "| errors | 3 | 2 | -1 |" in result
        # Zero delta
        assert "| warnings | 5 | 5 | 0 |" in result

    def test_positive_delta_has_plus_sign(self):
        qa = {
            "current": {"errors": 5},
            "baseline": {"errors": 3},
            "delta": {"errors": 2},
        }
        result = _format_qa_section(qa)
        assert "| errors | 3 | 5 | +2 |" in result

    def test_bullet_list_when_no_baseline(self):
        qa = {
            "current": {"errors": 2, "warnings": 5},
            "baseline": None,
            "delta": {},
        }
        result = _format_qa_section(qa)
        assert "| metric |" not in result
        assert "- errors: 2" in result
        assert "- warnings: 5" in result

    def test_section_header_present(self):
        qa = {"current": {"errors": 0}, "baseline": None, "delta": {}}
        result = _format_qa_section(qa)
        assert result.startswith("## Publisher QA")

    def test_ends_with_newline(self):
        qa = {"current": {"errors": 0}, "baseline": None, "delta": {}}
        result = _format_qa_section(qa)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# main() – file-based integration tests
# ---------------------------------------------------------------------------


class TestMainSingleMode:
    def test_writes_commit_and_pr_files(self, tmp_path: Path):
        ticket_path = make_ticket_json(tmp_path)
        synopsis_path = tmp_path / "synopsis.txt"
        synopsis_path.write_text("Implemented the feature as described in the ticket.")
        out_commit = tmp_path / "out" / "FHIR-99.commit.txt"
        out_pr = tmp_path / "out" / "FHIR-99.pr.md"

        rc = main(
            [
                "--ticket", str(ticket_path),
                "--synopsis-file", str(synopsis_path),
                "--out-commit", str(out_commit),
                "--out-pr", str(out_pr),
            ]
        )

        assert rc == 0
        assert out_commit.exists(), "commit file should be written"
        assert out_pr.exists(), "PR file should be written"

        commit_text = out_commit.read_text()
        assert "FHIR-99:" in commit_text
        assert "Implemented the feature" in commit_text

        pr_text = out_pr.read_text()
        assert "FHIR-99" in pr_text

    def test_missing_required_args_returns_2(self, tmp_path: Path):
        out_pr = tmp_path / "out.pr.md"
        rc = main(["--out-pr", str(out_pr)])
        assert rc == 2

    def test_files_changed_appear_in_pr(self, tmp_path: Path):
        ticket_path = make_ticket_json(tmp_path)
        synopsis_path = tmp_path / "synopsis.txt"
        synopsis_path.write_text("Did a thing.")
        out_commit = tmp_path / "commit.txt"
        out_pr = tmp_path / "pr.md"

        rc = main(
            [
                "--ticket", str(ticket_path),
                "--synopsis-file", str(synopsis_path),
                "--files-changed", "source/foo.xml\nsource/bar.xml",
                "--out-commit", str(out_commit),
                "--out-pr", str(out_pr),
            ]
        )

        assert rc == 0
        pr_text = out_pr.read_text()
        assert "source/foo.xml" in pr_text
        assert "source/bar.xml" in pr_text


class TestMainBatchMode:
    def test_writes_pr_file(self, tmp_path: Path):
        # Write two ticket JSON files into a cache dir
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        make_ticket_json(cache_dir, key="FHIR-10", summary="First batch ticket")
        make_ticket_json(cache_dir, key="FHIR-11", summary="Second batch ticket")

        synopses = {
            "FHIR-10": {"synopsis": "Fixed the first one.", "files": ["a.xml"]},
            "FHIR-11": {"synopsis": "Fixed the second one.", "files": ["b.xml"]},
        }
        synopses_path = tmp_path / "synopses.json"
        synopses_path.write_text(json.dumps(synopses))

        out_pr = tmp_path / "batch.pr.md"

        rc = main(
            [
                "--batch",
                "--tickets", "FHIR-10,FHIR-11",
                "--synopses-file", str(synopses_path),
                "--cache-dir", str(cache_dir),
                "--out-pr", str(out_pr),
            ]
        )

        assert rc == 0
        assert out_pr.exists(), "batch PR file should be written"
        pr_text = out_pr.read_text()
        assert "FHIR-10" in pr_text
        assert "FHIR-11" in pr_text
        assert "Fixed the first one." in pr_text
        assert "Fixed the second one." in pr_text

    def test_missing_tickets_arg_returns_2(self, tmp_path: Path):
        out_pr = tmp_path / "out.pr.md"
        rc = main(["--batch", "--out-pr", str(out_pr)])
        assert rc == 2
