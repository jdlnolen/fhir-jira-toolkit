"""Tests for fetch_ticket.py."""

from __future__ import annotations

import io
import json
from http.client import HTTPMessage
from unittest.mock import MagicMock

import pytest

import fetch_ticket
from fetch_ticket import (
    _IssuePageExtractor,
    _fallback_regex_extract,
    cache_issue,
    fetch_filter_keys,
    fetch_issue,
    normalized_summary,
    parse_issue_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(body: str, charset: str = "utf-8"):
    """Return a mock urllib response context-manager."""
    encoded = body.encode(charset)
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    headers = MagicMock(spec=HTTPMessage)
    headers.get_content_charset.return_value = charset
    mock_resp.headers = headers
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# 1. _IssuePageExtractor: core fields from minimal HTML
# ---------------------------------------------------------------------------


class TestIssuePageExtractorCoreFields:
    def test_extracts_summary(self):
        html = '<h1 id="summary-val">My ticket summary</h1>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core["summary"] == "My ticket summary"

    def test_extracts_status(self):
        html = '<span id="status-val"><span>Closed</span></span>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core["status"] == "Closed"

    def test_extracts_resolution(self):
        html = '<span id="resolution-val">Persuasive with Modification</span>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core["resolution"] == "Persuasive with Modification"

    def test_extracts_issuetype(self):
        html = '<span id="type-val">Change Request</span>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core["issuetype"] == "Change Request"

    def test_extracts_all_core_fields_together(self):
        html = (
            '<h1 id="summary-val">Summary text</h1>'
            '<span id="status-val"><span>Open</span></span>'
            '<span id="resolution-val">Unresolved</span>'
            '<span id="type-val">Bug</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core["summary"] == "Summary text"
        assert p.core["status"] == "Open"
        assert p.core["resolution"] == "Unresolved"
        assert p.core["issuetype"] == "Bug"


# ---------------------------------------------------------------------------
# 2. _IssuePageExtractor: custom fields via label/value pairing
# ---------------------------------------------------------------------------


class TestIssuePageExtractorCustomFields:
    def test_pairs_label_with_value(self):
        html = (
            '<strong class="name">Specification:</strong>'
            '<span class="value">FHIR Core (FHIR)</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields["Specification"] == "FHIR Core (FHIR)"

    def test_strips_colon_from_label(self):
        html = (
            '<strong class="name">Related URL:</strong>'
            '<span class="value">https://hl7.org/fhir/</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert "Related URL" in p.fields
        assert p.fields["Related URL"] != ""

    def test_pairs_label_with_val_id(self):
        html = (
            '<strong class="name">Workflow:</strong>'
            '<span id="workflow-val">Approved</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields.get("Workflow") == "Approved"

    def test_multiple_custom_fields(self):
        html = (
            '<strong class="name">Specification:</strong>'
            '<span class="value">FHIR Core</span>'
            '<strong class="name">Resolution Description:</strong>'
            '<span class="value">Fixed in ballot</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields["Specification"] == "FHIR Core"
        assert p.fields["Resolution Description"] == "Fixed in ballot"


# ---------------------------------------------------------------------------
# 3. _IssuePageExtractor: pending label preserved through empty value element
# ---------------------------------------------------------------------------


class TestIssuePageExtractorPendingLabel:
    def test_empty_value_keeps_label_pending(self):
        """When a value element is empty, the label stays pending for the next one."""
        html = (
            '<strong class="name">Specification:</strong>'
            '<span class="value"></span>'       # empty — label should survive
            '<span class="value">FHIR Core</span>'  # real value
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields.get("Specification") == "FHIR Core"

    def test_nonempty_value_clears_label(self):
        """Once a non-empty value is found, label is consumed and not reused."""
        html = (
            '<strong class="name">Spec:</strong>'
            '<span class="value">FHIR Core</span>'
            '<span class="value">Should not be paired</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields.get("Spec") == "FHIR Core"
        assert "Should not be paired" not in p.fields.values()

    def test_whitespace_only_value_keeps_label_pending(self):
        """Whitespace-only value content is treated as empty."""
        html = (
            '<strong class="name">Disposition:</strong>'
            '<span class="value">   </span>'
            '<span class="value">Persuasive</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields.get("Disposition") == "Persuasive"


# ---------------------------------------------------------------------------
# 4. _IssuePageExtractor: description text and embedded link hrefs
# ---------------------------------------------------------------------------


class TestIssuePageExtractorDescription:
    def test_captures_description_text_by_id(self):
        html = '<div id="description-val">The spec needs an example here.</div>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.description_text == "The spec needs an example here."

    def test_captures_description_text_by_class(self):
        html = '<div class="user-content-block">Block body text.</div>'
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.description_text == "Block body text."

    def test_captures_link_href_inside_description(self):
        html = (
            '<div id="description-val">'
            'See <a href="https://hl7.org/fhir/obs.html">this page</a>.'
            '</div>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert "https://hl7.org/fhir/obs.html" in p.description_links

    def test_ignores_relative_links_in_description(self):
        html = (
            '<div id="description-val">'
            '<a href="/browse/FHIR-1">FHIR-1</a>'
            '</div>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.description_links == []

    def test_captures_multiple_links(self):
        html = (
            '<div id="description-val">'
            '<a href="https://example.com/a">a</a>'
            '<a href="https://example.com/b">b</a>'
            '</div>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert len(p.description_links) == 2


# ---------------------------------------------------------------------------
# 5. _IssuePageExtractor: void elements don't corrupt depth tracking
# ---------------------------------------------------------------------------


class TestIssuePageExtractorVoidElements:
    def test_br_inside_core_field_does_not_break_depth(self):
        """<br> inside a field should not decrement depth and close captures early."""
        html = (
            '<h1 id="summary-val">'
            'Line one<br>Line two'
            '</h1>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core.get("summary") is not None
        assert "Line one" in p.core["summary"]
        assert "Line two" in p.core["summary"]

    def test_img_inside_description_does_not_break_depth(self):
        html = (
            '<div id="description-val">'
            'Before<img src="x.png" alt="x">After'
            '</div>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert "Before" in p.description_text
        assert "After" in p.description_text

    def test_br_between_label_and_value_does_not_break_pairing(self):
        """<br> between <strong class="name"> close and the value span should be harmless."""
        html = (
            '<strong class="name">Spec:</strong>'
            '<br>'
            '<span class="value">FHIR Core</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.fields.get("Spec") == "FHIR Core"

    def test_input_void_element_in_nested_context(self):
        """input is a void element — should not change depth."""
        html = (
            '<span id="status-val">'
            '<input type="hidden" value="x">'
            'Active'
            '</span>'
        )
        p = _IssuePageExtractor()
        p.feed(html)
        p.close()
        assert p.core.get("status") == "Active"


# ---------------------------------------------------------------------------
# 6. _fallback_regex_extract fills in fields the parser misses
# ---------------------------------------------------------------------------


class TestFallbackRegexExtract:
    def test_extracts_summary(self):
        html = '<h1 id="summary-val" class="issue-header">Fallback summary</h1>'
        result = _fallback_regex_extract(html)
        assert result["summary"] == "Fallback summary"

    def test_extracts_status(self):
        html = '<span id="status-val"><span class="jira-issue-status-lozenge">Closed</span></span>'
        result = _fallback_regex_extract(html)
        assert result["status"] == "Closed"

    def test_extracts_resolution(self):
        html = '<span id="resolution-val">Persuasive</span>'
        result = _fallback_regex_extract(html)
        assert result["resolution"] == "Persuasive"

    def test_extracts_issuetype(self):
        html = '<span id="type-val">Change Request</span>'
        result = _fallback_regex_extract(html)
        assert result["issuetype"] == "Change Request"

    def test_strips_inner_tags(self):
        html = '<span id="resolution-val"><strong>Persuasive</strong> with Modification</span>'
        result = _fallback_regex_extract(html)
        assert result["resolution"] == "Persuasive with Modification"

    def test_omits_empty_fields(self):
        """Fields with no match are omitted from the result dict."""
        result = _fallback_regex_extract("<html></html>")
        assert "summary" not in result
        assert "status" not in result


# ---------------------------------------------------------------------------
# 7. parse_issue_html: merges parser and fallback results
# ---------------------------------------------------------------------------


class TestParseIssueHtml:
    def test_uses_parser_result_when_present(self):
        html = '<h1 id="summary-val">Parser summary</h1>'
        result = parse_issue_html("FHIR-1", html)
        assert result["summary"] == "Parser summary"

    def test_falls_back_for_missing_field(self):
        """Parser won't capture status here (wrong nesting), fallback should."""
        html = '<span id="status-val">Open</span>'
        result = parse_issue_html("FHIR-1", html)
        # Either parser or fallback fills status
        assert result["status"] == "Open"

    def test_resolution_defaults_to_unresolved(self):
        result = parse_issue_html("FHIR-99", "<html></html>")
        assert result["resolution"] == "(unresolved)"

    def test_includes_standard_keys(self):
        result = parse_issue_html("FHIR-1", "<html></html>")
        for k in ("key", "url", "summary", "status", "resolution", "issuetype", "description", "fields", "fetched_at"):
            assert k in result

    def test_key_and_url_set_correctly(self):
        result = parse_issue_html("FHIR-42", "<html></html>")
        assert result["key"] == "FHIR-42"
        assert result["url"] == "https://jira.hl7.org/browse/FHIR-42"

    def test_custom_fields_included(self):
        html = (
            '<strong class="name">Specification:</strong>'
            '<span class="value">FHIR Core</span>'
        )
        result = parse_issue_html("FHIR-1", html)
        assert result["fields"].get("Specification") == "FHIR Core"


# ---------------------------------------------------------------------------
# 8. parse_issue_html: _description_links stored when no Related URL
# ---------------------------------------------------------------------------


class TestParseIssueHtmlDescriptionLinks:
    def test_stores_description_links_when_no_related_url(self):
        html = (
            '<div id="description-val">'
            '<a href="https://hl7.org/fhir/obs.html">obs</a>'
            '</div>'
        )
        result = parse_issue_html("FHIR-1", html)
        assert "_description_links" in result["fields"]
        assert "https://hl7.org/fhir/obs.html" in result["fields"]["_description_links"]

    def test_does_not_store_description_links_when_related_url_present(self):
        html = (
            '<div id="description-val">'
            '<a href="https://hl7.org/fhir/obs.html">obs</a>'
            '</div>'
            '<strong class="name">Related URL:</strong>'
            '<span class="value">https://hl7.org/fhir/explicit.html</span>'
        )
        result = parse_issue_html("FHIR-1", html)
        assert "_description_links" not in result["fields"]

    def test_limits_description_links_to_five(self):
        links = "".join(
            f'<a href="https://example.com/{i}">link{i}</a>'
            for i in range(10)
        )
        html = f'<div id="description-val">{links}</div>'
        result = parse_issue_html("FHIR-1", html)
        stored = result["fields"].get("_description_links", "")
        assert stored.count("https://") <= 5


# ---------------------------------------------------------------------------
# 9. fetch_issue: rejects invalid key format
# ---------------------------------------------------------------------------


class TestFetchIssueValidation:
    @pytest.mark.parametrize("bad_key", [
        "../../evil",
        "",
        "FHIR 12345",
        "fhir-12345",       # lowercase
        "FHIR-",            # missing number
        "-12345",           # missing project
        "FHIR-12345-extra", # too many parts
    ])
    def test_rejects_invalid_key(self, bad_key):
        with pytest.raises(ValueError, match="Invalid ticket key format"):
            fetch_issue(bad_key)


# ---------------------------------------------------------------------------
# 10. fetch_issue: accepts valid key format (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchIssueValidKeys:
    @pytest.mark.parametrize("key", ["FHIR-12345", "ABC-1"])
    def test_accepts_valid_key(self, monkeypatch, key):
        minimal_html = (
            f'<h1 id="summary-val">Test {key}</h1>'
            '<span id="status-val">Open</span>'
        )
        mock_resp = _make_mock_response(minimal_html)
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=30: mock_resp)

        result = fetch_issue(key)
        assert result["key"] == key
        assert result["url"] == f"https://jira.hl7.org/browse/{key}"

    def test_correct_url_requested(self, monkeypatch):
        captured = {}

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            return _make_mock_response('<h1 id="summary-val">S</h1>')

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        fetch_issue("FHIR-99")
        assert captured["url"] == "https://jira.hl7.org/browse/FHIR-99"


# ---------------------------------------------------------------------------
# 11. fetch_filter_keys: rejects non-numeric filter ID
# ---------------------------------------------------------------------------


class TestFetchFilterKeysValidation:
    @pytest.mark.parametrize("bad_id", [
        "abc",
        "24101x",
        "24 101",
        "../etc",
        "",
    ])
    def test_rejects_non_numeric_filter_id(self, bad_id):
        with pytest.raises(ValueError, match="Invalid filter ID format"):
            fetch_filter_keys(bad_id)


# ---------------------------------------------------------------------------
# 12. fetch_filter_keys: accepts numeric filter ID (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchFilterKeysNumericId:
    def test_parses_keys_from_xml(self, monkeypatch):
        xml_body = (
            "<?xml version='1.0'?><rss>"
            "<item><key id='1'>FHIR-100</key></item>"
            "<item><key id='2'>FHIR-200</key></item>"
            "<item><key id='3'>FHIR-100</key></item>"  # duplicate
            "</rss>"
        )
        mock_resp = _make_mock_response(xml_body)
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=30: mock_resp)

        keys = fetch_filter_keys("24101")
        assert sorted(keys) == ["FHIR-100", "FHIR-200"]

    def test_correct_url_requested(self, monkeypatch):
        captured = {}

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            return _make_mock_response("<rss></rss>")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        fetch_filter_keys("99999")
        assert "99999" in captured["url"]
        assert "SearchRequest-99999.xml" in captured["url"]

    def test_returns_sorted_unique_keys(self, monkeypatch):
        xml_body = (
            "<rss>"
            "<key>FHIR-300</key><key>FHIR-100</key><key>FHIR-200</key><key>FHIR-100</key>"
            "</rss>"
        )
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=30: _make_mock_response(xml_body),
        )
        keys = fetch_filter_keys("1")
        assert keys == sorted(set(keys))


# ---------------------------------------------------------------------------
# 13. cache_issue: writes JSON to correct path under cache dir
# ---------------------------------------------------------------------------


class TestCacheIssue:
    def test_creates_json_file(self, tmp_path, sample_ticket):
        path = cache_issue(sample_ticket, tmp_path)
        assert path.exists()
        assert path.name == "FHIR-12345.json"

    def test_json_content_matches_issue(self, tmp_path, sample_ticket):
        path = cache_issue(sample_ticket, tmp_path)
        loaded = json.loads(path.read_text())
        assert loaded == sample_ticket

    def test_creates_cache_dir_if_missing(self, tmp_path, sample_ticket):
        nested = tmp_path / "deep" / "cache"
        cache_issue(sample_ticket, nested)
        assert nested.is_dir()
        assert (nested / "FHIR-12345.json").exists()

    def test_returns_correct_path(self, tmp_path, sample_ticket):
        returned = cache_issue(sample_ticket, tmp_path)
        expected = tmp_path / "FHIR-12345.json"
        assert returned == expected


# ---------------------------------------------------------------------------
# 14. normalized_summary: formats output with all standard fields
# ---------------------------------------------------------------------------


class TestNormalizedSummary:
    def test_contains_key_header(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "=== FHIR-12345 ===" in out

    def test_contains_summary_line(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "Summary    : Add example for Quantity with SI unit" in out

    def test_contains_status_line(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "Status     : Closed" in out

    def test_contains_resolution_line(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "Resolution : Persuasive" in out

    def test_contains_type_line(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "Type       : Change Request" in out

    def test_contains_custom_fields(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "Specification" in out
        assert "FHIR Core (FHIR)" in out

    def test_contains_description_section(self, sample_ticket):
        out = normalized_summary(sample_ticket)
        assert "--- Description ---" in out
        assert "The spec should include an example" in out

    def test_omits_private_fields(self, sample_ticket):
        """Fields starting with _ should not appear in the output."""
        sample_ticket["fields"]["_description_links"] = "https://example.com"
        out = normalized_summary(sample_ticket)
        assert "_description_links" not in out

    def test_no_description_section_when_empty(self):
        issue = {
            "key": "FHIR-1",
            "summary": "S",
            "status": "Open",
            "resolution": "(unresolved)",
            "issuetype": "",
            "description": "",
            "fields": {},
        }
        out = normalized_summary(issue)
        assert "--- Description ---" not in out
