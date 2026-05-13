---
title: "feat: Add test suite for Python helper scripts"
status: active
created: 2026-05-13
plan_depth: lightweight
origin: code review findings (2026-05-13 session)
requirements:
  - R1: All four Python scripts have unit test coverage for their core logic
  - R2: Test infrastructure is minimal — pytest only, no additional runtime deps
  - R3: Tests run without network access or external dependencies
  - R4: High-risk code paths identified in the code review have explicit test coverage
---

# feat: Add test suite for Python helper scripts

## Summary

Add a pytest-based test suite for the four Python helper scripts in the fhir-jira-toolkit plugin. These scripts handle JIRA ticket fetching (HTML scraping), repository resolution, QA report parsing, and commit/PR message formatting. A code review identified zero test coverage as the highest-priority gap, with the HTML parser, resolution tie-breaking, and QA schema detection as the riskiest untested code paths.

## Problem Frame

The plugin ships four Python scripts that handle security-sensitive operations (URL construction from user input, HTML parsing of external content, file path construction) and correctness-critical logic (QA regression detection, spec-name matching). None of these have tests. The code review found multiple bugs that would have been caught by even basic test coverage (e.g., `_merge_maps` destroying list fields, `counts()` falling through to false-green on unknown schemas).

## Scope Boundaries

**In scope:**
- Unit tests for all pure functions in all four scripts
- Integration-style tests for `main(argv)` entry points using `tmp_path`
- Shared fixtures for common test data (ticket dicts, repo-map dicts, QA schema variants)
- Minimal project config (`pyproject.toml` with pytest dependency)

**Out of scope:**
- End-to-end tests against live JIRA (network-dependent)
- CI/CD pipeline setup (no `.github/workflows/` — can be a follow-up)
- Tests for the Markdown command/skill files (instruction-prose, not executable)
- Performance testing

### Deferred to Follow-Up Work

- CI pipeline with automated test runs on push
- HTML fixture files captured from real JIRA pages for regression testing
- Integration tests with a mock HTTP server for the full fetch-parse-cache flow

## Key Technical Decisions

1. **Test layout: `tests/` at repo root.** Not inside `plugins/` — keeps test infrastructure separate from the distributed plugin. Pytest discovers tests from the root automatically.

2. **Import strategy: direct import, not subprocess.** All scripts expose `main(argv: list[str]) -> int` and pure functions at module level. Tests import these directly. `sys.path` manipulation in `conftest.py` adds the scripts directory.

3. **Network isolation via `monkeypatch`.** Only `fetch_ticket.py` touches the network. Tests replace `urllib.request.urlopen` with a mock returning pre-built HTML strings. No mock HTTP server needed.

4. **Fixture data as inline dicts and strings.** Minimal HTML fragments, ticket dicts, and QA JSON dicts defined inline in test files or shared via `conftest.py`. The shipped `repo-map.json` can be loaded as a golden fixture for resolve_repo tests.

5. **No `requirements.txt` — use `pyproject.toml`.** Single source of truth for project metadata and test dependencies. `pip install -e ".[test]"` installs pytest.

## Implementation Units

### U1. Project config and test infrastructure

**Goal:** Establish minimal pytest infrastructure so tests can be written and run.

**Requirements:** R2

**Dependencies:** None

**Files:**
- `pyproject.toml` (create)
- `tests/conftest.py` (create)

**Approach:** Create `pyproject.toml` with `[project]` metadata (name, version, python-requires >= 3.9) and `[project.optional-dependencies] test = ["pytest"]`. The `conftest.py` provides shared fixtures: `sample_ticket` (minimal valid ticket dict), `sample_repo_map` (minimal repo map with 2 specs), and `qa_schema_variants` (dict of the 4 QA JSON shapes). Add `sys.path` insertion for the scripts directory so tests can `import fetch_ticket` etc. without package installation.

**Patterns to follow:** Standard pytest project layout. The scripts use `from __future__ import annotations` so imports work on 3.9+.

**Test scenarios:**
- Verify `pytest --collect-only` finds test files (smoke test for infrastructure)

**Verification:** `pip install -e ".[test]" && pytest --collect-only` succeeds and lists test modules.

### U2. Tests for `parse_qa.py`

**Goal:** Cover the QA parsing logic — the most critical untested code (false-green regression detection is a safety issue).

**Requirements:** R1, R3, R4

**Dependencies:** U1

**Files:**
- `tests/test_parse_qa.py` (create)
- `plugins/fhir-jira/skills/fhir-jira-workflow/scripts/parse_qa.py` (read-only reference)

**Approach:** Parametrize `counts()` using the `qa_schema_variants` fixture from `conftest.py`. Test `delta()` and `render()` as pure functions. Test `main(argv)` with `tmp_path` files for exit code verification.

**Test scenarios:**
- `counts()` with newer top-level keys (`errs`, `warnings`, `hints`, `links`) returns correct values
- `counts()` with older top-level keys (`errors`, `warnings`, `info`, `brokenlinks`) returns correct values
- `counts()` with `summary` subobject returns correct values
- `counts()` with per-file `messages` array aggregates error/warning/info/broken-link levels correctly
- `counts()` with unrecognized schema (empty dict, no matching keys) returns all-zeros AND prints warning to stderr
- `counts()` with `None` or non-numeric values in count fields returns 0 via `_to_int` (not an exception)
- `delta()` with baseline returns correct deltas and `regressed=True` when errors increase
- `delta()` without baseline returns `None` deltas and `regressed=False`
- `render()` with baseline shows the table format with +/- signs
- `render()` without baseline shows snapshot format
- `main(["--current", valid_path])` exits 0 when no regression
- `main(["--current", valid_path, "--baseline", baseline_path])` exits 1 when errors increased
- `main(["--current", missing_path])` exits 2 (invalid input)
- `main(["--current", valid_path, "--out", out_path])` writes delta JSON to disk

**Verification:** `pytest tests/test_parse_qa.py -v` passes. All 4 schema branches exercised.

### U3. Tests for `resolve_repo.py`

**Goal:** Cover the resolution logic — the most complex branching code, including tie-breaking and the recently-fixed merge behavior.

**Requirements:** R1, R3, R4

**Dependencies:** U1

**Files:**
- `tests/test_resolve_repo.py` (create)
- `plugins/fhir-jira/skills/fhir-jira-workflow/scripts/resolve_repo.py` (read-only reference)

**Approach:** Test `resolve_for_ticket()`, `_merge_maps()`, `_normalize_spec_value()`, `_candidate_urls()`, and `resolve_local_path()` as pure functions with synthetic dicts. Test `main(argv)` with `tmp_path` for `--ticket`, `--list`, and `--group` modes.

**Test scenarios:**
- `resolve_for_ticket()` matches single spec by Specification field name
- `resolve_for_ticket()` resolves ambiguity via longest-match tie-breaking (e.g., "FHIR Core" vs "US Core" when spec value is "FHIR Core (FHIR)")
- `resolve_for_ticket()` returns ambiguous error when top matches are truly tied
- `resolve_for_ticket()` falls back to URL pattern matching when Specification field is empty
- `resolve_for_ticket()` with new URL ambiguity detection: returns error when multiple specs match the same URL
- `resolve_for_ticket()` returns unresolved when neither Specification nor URL matches
- `_merge_maps()` preserves base `names` array when override only sets `local_path` (the recently-fixed bug)
- `_merge_maps()` extends `names` with new entries from override without duplicates
- `_merge_maps()` overrides scalar fields like `default_branch` and `publisher`
- `_merge_maps()` overrides `default_clone_root` from top level
- `_normalize_spec_value()` handles string, dict with `value` key, list, and None
- `_candidate_urls()` extracts URLs from Related URL field, description, and _description_links
- `resolve_local_path()` uses explicit `local_path` when present
- `resolve_local_path()` falls back to `default_clone_root / repo_name`
- `resolve_local_path()` falls back to `~/dev/hl7/repo_name` when no root specified
- `main(["--group", paths])` groups tickets by repo and reports unresolved separately
- `main(["--group", paths])` handles corrupt ticket JSON gracefully (routes to unresolved, not crash)
- `load_map()` raises `FileNotFoundError` (not `SystemExit`) when repo-map is missing

**Verification:** `pytest tests/test_resolve_repo.py -v` passes. Tie-breaking and merge logic exercised.

### U4. Tests for `fetch_ticket.py`

**Goal:** Cover HTML parsing and input validation without network access.

**Requirements:** R1, R3, R4

**Dependencies:** U1

**Files:**
- `tests/test_fetch_ticket.py` (create)
- `plugins/fhir-jira/skills/fhir-jira-workflow/scripts/fetch_ticket.py` (read-only reference)

**Approach:** Build minimal HTML fragments that exercise the parser's depth-tracking, core-field extraction, and custom-field label/value pairing. Test `parse_issue_html()` as a pure function. Test input validation (`_TICKET_KEY_RE`, `_FILTER_ID_RE`). Mock `urllib.request.urlopen` for `fetch_issue()` and `cache_issue()` tests.

**Test scenarios:**
- `_IssuePageExtractor` extracts core fields (`summary-val`, `status-val`, `resolution-val`, `type-val`) from minimal HTML
- `_IssuePageExtractor` extracts custom fields by pairing `<strong class="name">Label:</strong>` with value elements
- `_IssuePageExtractor` preserves pending label through empty value elements (the recently-fixed bug)
- `_IssuePageExtractor` captures description text and embedded link hrefs
- `_IssuePageExtractor` handles void elements (`<br>`, `<img>`) without corrupting depth tracking
- `_fallback_regex_extract()` fills in fields the parser misses
- `parse_issue_html()` merges parser and fallback results correctly
- `parse_issue_html()` stores description links as `_description_links` synthetic field when no Related URL exists
- `fetch_issue()` rejects invalid key format (`../../evil`, empty string, `FHIR 12345`) with `ValueError`
- `fetch_issue()` accepts valid key format (`FHIR-12345`, `ABC-1`)
- `fetch_filter_keys()` rejects non-numeric filter ID with `ValueError`
- `fetch_filter_keys()` accepts numeric filter ID (`24101`)
- `cache_issue()` writes JSON to correct path under cache dir
- `normalized_summary()` formats output with all standard fields
- `main()` with mocked HTTP returns cached JSON and prints summary

**Verification:** `pytest tests/test_fetch_ticket.py -v` passes. Parser depth-tracking and input validation exercised.

### U5. Tests for `format_messages.py`

**Goal:** Cover message formatting — the lowest-risk scripts but still needing basic coverage for the edge cases found in code review.

**Requirements:** R1, R3, R4

**Dependencies:** U1

**Files:**
- `tests/test_format_messages.py` (create)
- `plugins/fhir-jira/skills/fhir-jira-workflow/scripts/format_messages.py` (read-only reference)

**Approach:** All formatting functions are pure string transformations. Test with synthetic ticket dicts and synopsis strings. Code-review findings (markdown injection via backticks, `wrap_body` per-line check) are explicitly covered.

**Test scenarios:**
- `truncate_subject()` returns full text when under 72 chars
- `truncate_subject()` truncates with ellipsis at exactly 72 chars including prefix
- `truncate_subject()` handles edge case where key prefix alone exceeds limit
- `wrap_body()` wraps normal paragraphs at 72 chars
- `wrap_body()` preserves paragraphs containing blockquote or list lines (per-line check, not whole-paragraph)
- `wrap_body()` preserves multi-paragraph structure with blank-line separators
- `_escape_backticks()` escapes backtick characters in file names
- `_escape_md_link_text()` escapes `]` and `)` characters
- `format_commit()` produces subject line, blank line, body, and trailers in correct format
- `format_pr_single()` produces correct markdown with ticket link, synopsis, files, and QA table
- `format_pr_single()` omits QA section when `qa_delta` is None
- `format_pr_batch()` produces per-ticket sections with synopsis, files, and ticket links
- `_format_qa_section()` renders markdown table when baseline exists
- `_format_qa_section()` renders bullet list when no baseline
- `main(["--ticket", path, "--synopsis-file", path, "--out-commit", path, "--out-pr", path])` in single mode writes both commit and PR files to disk
- `main(["--batch", "--tickets", keys, "--synopses-file", path, "--out-pr", path])` in batch mode writes PR file to disk

**Verification:** `pytest tests/test_format_messages.py -v` passes.

## Build Sequence

```
U1 (infrastructure) → U2 (parse_qa) ─┐
                    → U3 (resolve_repo) ─┤ (parallel, both depend on U1)
                    → U4 (fetch_ticket)  ─┤
                    → U5 (format_messages)┘
```

U2-U5 are independent of each other and can be implemented in any order after U1. Priority order by risk: U2 (false-green QA) → U3 (resolution bugs) → U4 (HTML parsing + security) → U5 (formatting).
