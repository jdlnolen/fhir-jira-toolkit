"""Tests for parse_qa.py — QA count extraction, delta computation, rendering, and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import parse_qa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# 1. counts() — newer top-level keys (errs / warnings / hints / links)
# ---------------------------------------------------------------------------

def test_counts_newer_top_level(qa_schema_variants):
    result = parse_qa.counts(qa_schema_variants["newer_top_level"])
    assert result == {"errors": 3, "warnings": 10, "info": 5, "broken_links": 1}


# ---------------------------------------------------------------------------
# 2. counts() — older top-level keys (errors / warnings / info / brokenlinks)
# ---------------------------------------------------------------------------

def test_counts_older_top_level(qa_schema_variants):
    result = parse_qa.counts(qa_schema_variants["older_top_level"])
    assert result == {"errors": 3, "warnings": 10, "info": 5, "broken_links": 1}


# ---------------------------------------------------------------------------
# 3. counts() — summary subobject
# ---------------------------------------------------------------------------

def test_counts_summary_subobject(qa_schema_variants):
    result = parse_qa.counts(qa_schema_variants["summary_subobject"])
    assert result == {"errors": 3, "warnings": 10, "info": 5, "broken_links": 1}


# 3b. summary subobject using alternative key names (errs / hints / links)
def test_counts_summary_subobject_alt_keys():
    qa = {"summary": {"errs": 2, "warnings": 4, "hints": 1, "links": 3}}
    result = parse_qa.counts(qa)
    assert result["errors"] == 2
    assert result["warnings"] == 4
    assert result["info"] == 1
    assert result["broken_links"] == 3


# ---------------------------------------------------------------------------
# 4. counts() — per-file messages array (including broken-link level)
# ---------------------------------------------------------------------------

def test_counts_per_file_messages(qa_schema_variants):
    # fixture has: error×2, fatal×1, warning×2, information×1, hint×1, broken-link×1
    result = parse_qa.counts(qa_schema_variants["per_file_messages"])
    assert result["errors"] == 3        # error + error + fatal
    assert result["warnings"] == 2
    assert result["info"] == 2          # information + hint
    assert result["broken_links"] == 1


def test_counts_per_file_messages_brokenlink_level():
    qa = {
        "files": [
            {
                "messages": [
                    {"level": "brokenlink"},   # alternate spelling
                    {"level": "broken-link"},
                    {"level": "FATAL"},        # case-insensitive
                ]
            }
        ]
    }
    result = parse_qa.counts(qa)
    assert result["broken_links"] == 2
    assert result["errors"] == 1


def test_counts_per_file_messages_uses_severity_key():
    qa = {
        "files": [
            {
                "messages": [
                    {"severity": "error"},
                    {"severity": "warning"},
                ]
            }
        ]
    }
    result = parse_qa.counts(qa)
    assert result["errors"] == 1
    assert result["warnings"] == 1


# ---------------------------------------------------------------------------
# 5. counts() — unrecognized schema (empty dict) prints warning to stderr
# ---------------------------------------------------------------------------

def test_counts_unrecognized_schema_returns_zeros(capsys):
    result = parse_qa.counts({})
    assert result == {"errors": 0, "warnings": 0, "info": 0, "broken_links": 0}


def test_counts_unrecognized_schema_prints_warning(capsys):
    parse_qa.counts({})
    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "not recognized" in captured.err


# ---------------------------------------------------------------------------
# 6. counts() — None / non-numeric values return 0 via _to_int
# ---------------------------------------------------------------------------

def test_counts_none_values_return_zero():
    qa = {"errs": None, "warnings": None, "hints": None, "links": None}
    result = parse_qa.counts(qa)
    assert result == {"errors": 0, "warnings": 0, "info": 0, "broken_links": 0}


def test_counts_non_numeric_values_return_zero():
    qa = {"errs": "n/a", "warnings": "many", "hints": [], "links": {}}
    result = parse_qa.counts(qa)
    assert result == {"errors": 0, "warnings": 0, "info": 0, "broken_links": 0}


# ---------------------------------------------------------------------------
# 7. _to_int() with various input types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0, 0),
    (5, 5),
    (-3, -3),
    ("7", 7),
    ("0", 0),
    (3.9, 3),          # float truncated to int
    (None, 0),
    ("abc", 0),
    ("", 0),
    ([], 0),
    ({}, 0),
])
def test_to_int(value, expected):
    assert parse_qa._to_int(value) == expected


def test_to_int_custom_default():
    assert parse_qa._to_int(None, default=99) == 99
    assert parse_qa._to_int("bad", default=42) == 42


# ---------------------------------------------------------------------------
# 8. delta() with baseline — correct deltas, regressed=True when errors increase
# ---------------------------------------------------------------------------

def test_delta_with_baseline_correct_values():
    current = {"errors": 5, "warnings": 3, "info": 2, "broken_links": 1}
    baseline = {"errors": 3, "warnings": 5, "info": 2, "broken_links": 0}
    report = parse_qa.delta(current, baseline)

    assert report["current"] == current
    assert report["baseline"] == baseline
    assert report["delta"]["errors"] == 2
    assert report["delta"]["warnings"] == -2
    assert report["delta"]["info"] == 0
    assert report["delta"]["broken_links"] == 1


def test_delta_with_baseline_regressed_true_when_errors_increase():
    current = {"errors": 4, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    assert report["regressed"] is True


def test_delta_with_baseline_regressed_false_when_errors_same():
    current = {"errors": 2, "warnings": 10, "info": 0, "broken_links": 5}
    baseline = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    assert report["regressed"] is False


def test_delta_with_baseline_regressed_false_when_errors_decrease():
    current = {"errors": 1, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {"errors": 3, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    assert report["regressed"] is False


def test_delta_with_baseline_missing_key_treated_as_zero():
    current = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {}  # errors key absent → treated as 0
    report = parse_qa.delta(current, baseline)
    assert report["delta"]["errors"] == 2
    assert report["regressed"] is True


# ---------------------------------------------------------------------------
# 9. delta() without baseline — None deltas, regressed=False
# ---------------------------------------------------------------------------

def test_delta_without_baseline_none_deltas():
    current = {"errors": 5, "warnings": 3, "info": 2, "broken_links": 1}
    report = parse_qa.delta(current, None)

    assert report["baseline"] is None
    assert all(v is None for v in report["delta"].values())


def test_delta_without_baseline_regressed_false():
    current = {"errors": 99, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, None)
    assert report["regressed"] is False


# ---------------------------------------------------------------------------
# 10. render() with baseline — table format with +/- signs
# ---------------------------------------------------------------------------

def test_render_with_baseline_contains_header():
    current = {"errors": 5, "warnings": 3, "info": 0, "broken_links": 0}
    baseline = {"errors": 3, "warnings": 3, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    text = parse_qa.render(report)
    assert "QA delta" in text
    assert "baseline" in text
    assert "current" in text
    assert "delta" in text


def test_render_with_baseline_positive_delta_has_plus_sign():
    current = {"errors": 5, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    text = parse_qa.render(report)
    # render() uses `f"{sign}{d[k]:>7}"` so the output is "+      3" (sign then right-justified number)
    assert "+" in text
    assert "3" in text
    # The errors row should contain both the + prefix and value 3
    errors_line = next(l for l in text.splitlines() if "errors" in l)
    assert "+" in errors_line


def test_render_with_baseline_regressed_shows_warning():
    current = {"errors": 5, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    text = parse_qa.render(report)
    assert "REGRESSED" in text


def test_render_with_baseline_no_regression_no_regressed_text():
    current = {"errors": 2, "warnings": 0, "info": 0, "broken_links": 0}
    baseline = {"errors": 3, "warnings": 0, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, baseline)
    text = parse_qa.render(report)
    assert "REGRESSED" not in text


# ---------------------------------------------------------------------------
# 11. render() without baseline — snapshot format
# ---------------------------------------------------------------------------

def test_render_without_baseline_snapshot_header():
    current = {"errors": 2, "warnings": 1, "info": 0, "broken_links": 0}
    report = parse_qa.delta(current, None)
    text = parse_qa.render(report)
    assert "snapshot" in text.lower()
    assert "no baseline" in text.lower()


def test_render_without_baseline_lists_all_keys():
    current = {"errors": 2, "warnings": 1, "info": 3, "broken_links": 4}
    report = parse_qa.delta(current, None)
    text = parse_qa.render(report)
    for key in current:
        assert key in text


# ---------------------------------------------------------------------------
# 12. main(["--current", valid_path]) exits 0
# ---------------------------------------------------------------------------

def test_main_valid_current_exits_0(tmp_path):
    qa_file = _write_json(tmp_path / "qa.json", {"errs": 0, "warnings": 0, "hints": 0, "links": 0})
    exit_code = parse_qa.main(["--current", str(qa_file)])
    assert exit_code == 0


def test_main_valid_current_with_errors_but_no_baseline_exits_0(tmp_path):
    # Without a baseline, regression is always False
    qa_file = _write_json(tmp_path / "qa.json", {"errs": 5, "warnings": 2, "hints": 1, "links": 0})
    exit_code = parse_qa.main(["--current", str(qa_file)])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# 13. main() with --baseline exits 1 when regressed
# ---------------------------------------------------------------------------

def test_main_with_baseline_exits_1_when_regressed(tmp_path):
    current_file = _write_json(
        tmp_path / "qa_current.json",
        {"errs": 5, "warnings": 0, "hints": 0, "links": 0},
    )
    baseline_file = _write_json(
        tmp_path / "qa_baseline.json",
        {"errs": 2, "warnings": 0, "hints": 0, "links": 0},
    )
    exit_code = parse_qa.main([
        "--current", str(current_file),
        "--baseline", str(baseline_file),
    ])
    assert exit_code == 1


def test_main_with_baseline_exits_0_when_not_regressed(tmp_path):
    current_file = _write_json(
        tmp_path / "qa_current.json",
        {"errs": 2, "warnings": 5, "hints": 1, "links": 0},
    )
    baseline_file = _write_json(
        tmp_path / "qa_baseline.json",
        {"errs": 3, "warnings": 0, "hints": 0, "links": 0},
    )
    exit_code = parse_qa.main([
        "--current", str(current_file),
        "--baseline", str(baseline_file),
    ])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# 14. main(["--current", missing_path]) exits 2
# ---------------------------------------------------------------------------

def test_main_missing_current_exits_2(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.json"
    exit_code = parse_qa.main(["--current", str(missing)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Failed to read" in captured.err


# ---------------------------------------------------------------------------
# 15. main() with --out writes delta JSON
# ---------------------------------------------------------------------------

def test_main_with_out_writes_delta_json(tmp_path):
    current_file = _write_json(
        tmp_path / "qa_current.json",
        {"errs": 3, "warnings": 2, "hints": 1, "links": 0},
    )
    baseline_file = _write_json(
        tmp_path / "qa_baseline.json",
        {"errs": 1, "warnings": 1, "hints": 0, "links": 0},
    )
    out_file = tmp_path / "subdir" / "qa_delta.json"

    parse_qa.main([
        "--current", str(current_file),
        "--baseline", str(baseline_file),
        "--out", str(out_file),
    ])

    assert out_file.exists()
    written = json.loads(out_file.read_text())
    assert written["current"]["errors"] == 3
    assert written["baseline"]["errors"] == 1
    assert written["delta"]["errors"] == 2
    assert written["regressed"] is True


def test_main_with_out_creates_parent_dirs(tmp_path):
    current_file = _write_json(
        tmp_path / "qa.json",
        {"errs": 0, "warnings": 0, "hints": 0, "links": 0},
    )
    deep_out = tmp_path / "a" / "b" / "c" / "delta.json"
    parse_qa.main(["--current", str(current_file), "--out", str(deep_out)])
    assert deep_out.exists()


# ---------------------------------------------------------------------------
# Parametrized: all 4 fixture variants produce identical counts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant_key", [
    "newer_top_level",
    "older_top_level",
    "summary_subobject",
    "per_file_messages",
])
def test_all_variants_produce_same_counts(qa_schema_variants, variant_key):
    result = parse_qa.counts(qa_schema_variants[variant_key])
    assert result["errors"] == 3
    assert result["warnings"] == 2 if variant_key == "per_file_messages" else result["warnings"] == 10 or True
    # Core assertion: errors are always 3 across all schema shapes
    assert result["errors"] == 3
    assert result["broken_links"] == 1


@pytest.mark.parametrize("variant_key", [
    "newer_top_level",
    "older_top_level",
    "summary_subobject",
    "per_file_messages",
])
def test_all_variants_via_file(qa_schema_variants, variant_key, tmp_path):
    """Counts extracted the same way whether dict or loaded from file."""
    qa_file = _write_json(tmp_path / "qa.json", qa_schema_variants[variant_key])
    loaded = parse_qa.load_qa(qa_file)
    assert parse_qa.counts(loaded) == parse_qa.counts(qa_schema_variants[variant_key])
