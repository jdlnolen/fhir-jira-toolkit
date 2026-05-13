---
title: "Hardening Claude Code Python Plugins for Production"
date: 2026-05-13
category: best-practices
module: fhir-jira-toolkit
problem_type: best_practice
component: tooling
severity: high
tags:
  - input-validation
  - testability
  - python
  - claude-code-plugin
  - security
  - config-merge
  - exception-design
  - version-management
applies_when:
  - "Building any Claude Code plugin with Python helper scripts"
  - "Working with external data formats that have schema variants"
  - "Designing CLI scripts that also need to be testable"
  - "Publishing plugins via GitHub marketplace"
---

# Hardening Claude Code Python Plugins for Production

## Context

A new Claude Code plugin (fhir-jira-toolkit) was built to automate HL7 FHIR JIRA ticket resolution across 4 Python helper scripts. A structured code review surfaced the gap between a working local prototype and a production-ready, GitHub-installable release:

- **Security**: Ticket keys and filter IDs passed directly into URLs and file paths with no validation — a path traversal and SSRF vector hiding in plain sight.
- **Correctness**: A config merge function used `dict.update()` on array fields, silently overwriting all base list values whenever a user applied even a single override.
- **Silent failures**: A QA JSON parser had 4 schema branches but no per-branch tests. An unrecognized schema variant returned all-zeros — a false-green that told callers "everything is fine."
- **Testability debt**: Scripts read `sys.argv` directly and raised `SystemExit` from library functions, making it impossible to write unit tests without subprocess overhead or mock patching.
- **No test coverage**: 0 tests shipped in the initial commit; bugs only surfaced through code review, not automation.

The practices below took the plugin from that state to 191 tests running in 0.08 s with no mocking infrastructure, clean security boundaries, and GitHub-installable release packaging.

## Guidance

### 1. Validate user-controlled identifiers at boundaries

Any identifier that originates from user input — ticket keys, filter IDs, project codes — and gets used in a URL or file path must be validated with a strict regex before any further use. Do this once, at the entry point of the function that first touches the identifier.

```python
import re

_TICKET_KEY_RE = re.compile(r'^[A-Z]+-\d+$')

def fetch_issue(key: str) -> dict:
    if not _TICKET_KEY_RE.fullmatch(key):
        raise ValueError(f"Invalid ticket key: {key!r}")
    url = f"{BASE_URL}/rest/api/2/issue/{key}"
    ...
```

`re.fullmatch` (not `re.match`) prevents bypasses like `FHIR-123/../../etc/passwd`. One regex check eliminates path traversal and SSRF in the same stroke.

### 2. Design scripts for testability from the start

Avoid reading `sys.argv` directly inside business logic. Use a `main(argv)` signature and keep business logic in pure functions that take and return plain dicts or strings.

```python
# Before — untestable without subprocess
def main():
    key = sys.argv[1]
    result = fetch_issue(key)
    ...

if __name__ == "__main__":
    main()

# After — testable with a direct call
def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: fetch_issue.py <ticket-key>", file=sys.stderr)
        return 1
    key = argv[1]
    result = fetch_issue(key)
    ...
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

With pure functions and `main(argv)`, 191 tests ran in 0.08 s with no mocking infrastructure — just direct function calls.

### 3. Test every schema variant of external formats

External data formats evolve. When parsing a format with known schema variants (like IG Publisher's qa.json), write at least one test per branch. Parametrize across all variants.

```python
@pytest.mark.parametrize("payload,expected_errors", [
    ({"messages": [{"level": "ERROR", "message": "x"}]}, 1),   # variant A
    ({"issues": {"error": 2}}, 2),                              # variant B
    ({"outcomes": [{"severity": "error"}]}, 1),                 # variant C
    ({"total": {"errors": 3, "warnings": 1}}, 3),               # variant D
    ({}, 0),                                                     # unrecognized — must not false-green silently
])
def test_parse_qa_json(payload, expected_errors):
    result = parse_qa_json(payload)
    assert result["errors"] == expected_errors
```

An unrecognized schema variant returning all-zeros is the most dangerous kind of silent failure: it reports success when nothing was actually checked.

### 4. Extend list fields; don't replace them during config merges

When merging user overrides onto shipped defaults, `dict.update()` replaces entire arrays. Users who add one entry to a list field silently lose all the base entries.

```python
# Before — destroys base list fields
def _merge_maps(existing: dict, spec: dict) -> dict:
    existing.update(spec)
    return existing

# After — extends lists, overwrites scalars
def _merge_maps(existing: dict, spec: dict) -> dict:
    for key, value in spec.items():
        if isinstance(value, list) and isinstance(existing.get(key), list):
            existing[key] = existing[key] + value   # extend, not replace
        else:
            existing[key] = value
    return existing
```

This is especially critical for fields like `names` and `url_patterns` where the base list contains required entries that downstream matching depends on.

### 5. Raise exceptions from library functions; let main() translate to exit codes

Functions called by both CLI entry points and tests should raise standard exceptions (`FileNotFoundError`, `ValueError`, `RuntimeError`), never `SystemExit`. `SystemExit` bypasses `pytest` assertions and makes exit codes non-deterministic from tests.

```python
# Before — SystemExit from a library function
def load_qa_file(path: str) -> dict:
    if not os.path.exists(path):
        raise SystemExit(f"qa file not found: {path}")

# After — raise a standard exception; let main() translate
def load_qa_file(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"qa file not found: {path}")

def main(argv: list[str]) -> int:
    try:
        data = load_qa_file(argv[1])
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    ...
```

This also makes documented exit codes reliable — the mapping from exception type to exit code lives in one place (main).

### 6. Add a version-check hook for GitHub-hosted plugins

A `SessionStart` hook that fetches the `VERSION` file from GitHub main and compares it against the local copy gives users low-friction update notifications without blocking session start.

```python
# hooks/session_start.py
import urllib.request, pathlib, sys

REMOTE = "https://raw.githubusercontent.com/org/repo/main/VERSION"
LOCAL  = pathlib.Path(__file__).parent.parent / "VERSION"

def check_version():
    try:
        with urllib.request.urlopen(REMOTE, timeout=5) as r:
            remote = r.read().decode().strip()
        local = LOCAL.read_text().strip()
        if remote != local:
            print(f"[fhir-jira] Update available: {local} → {remote}. "
                  f"See INSTALL.md for upgrade steps.")
    except Exception:
        pass   # fail-silent: never block session start

if __name__ == "__main__":
    check_version()
```

Key constraints: 5-second timeout, bare `except Exception: pass`, never blocks on failure.

### 7. Integrate with the knowledge ecosystem

Register two lightweight hooks in the workflow skill:

- **Step 0**: Check `ce-learnings-researcher` before starting work — prior solutions may already cover the problem.
- **Final step**: Recommend `/ce-compound` for non-obvious findings — surfaces institutional knowledge for future sessions.

Both steps degrade gracefully when the referenced skill is not installed. They are opt-in and add no required overhead.

## Why This Matters

- **Path traversal via unsanitized input** is a P0 security issue in any tool that constructs file paths or URLs from user-controlled identifiers. It is easy to introduce and invisible without a dedicated validation step.
- **False-green QA checks** are the most dangerous kind of silent failure. When a parser silently returns zero errors for an unrecognized schema, callers proceed confident the check passed — the failure mode is invisible by design.
- **Plugins without tests** accumulate bugs that only surface when users hit edge cases in production FHIR tickets, where the cost of failure is high and debugging context is cold.
- **Config merge bugs** silently break functionality for users who customized their setup and have no way to know that their base defaults were replaced. These are among the hardest bugs to diagnose because the tool appears to work until a specific downstream operation fails.
- **SystemExit from library functions** makes test suites unreliable — assertions never execute, exit codes become non-deterministic, and failures look like passing tests.

## When to Apply

- Building any Claude Code plugin with Python helper scripts
- Working with external data formats that have known schema variants (JSON formats from external tools, API response shapes that have evolved over versions)
- Designing CLI scripts that also need to be unit-testable
- Publishing plugins via GitHub marketplace or any public distribution channel
- Any project where config merging overlays user-supplied data onto shipped defaults with list fields

## Examples

### Input validation

```python
# Before: key used directly in URL and file path
def fetch_issue(key: str) -> dict:
    path = cache_dir / f"{key}.json"
    url = f"{BASE_URL}/rest/api/2/issue/{key}"
    ...

# After: reject at the boundary
_TICKET_KEY_RE = re.compile(r'^[A-Z]+-\d+$')

def fetch_issue(key: str) -> dict:
    if not _TICKET_KEY_RE.fullmatch(key):
        raise ValueError(f"Invalid ticket key: {key!r}")
    path = cache_dir / f"{key}.json"
    url = f"{BASE_URL}/rest/api/2/issue/{key}"
    ...
```

### Config merge preserving list fields

```python
# Before: dict.update destroys base list fields
existing = {"names": ["FHIR", "HL7"], "timeout": 30}
override = {"names": ["custom"]}
existing.update(override)
# existing["names"] is now ["custom"] — base entries silently gone

# After: per-key merge extends lists
for key, value in override.items():
    if isinstance(value, list) and isinstance(existing.get(key), list):
        existing[key] = existing[key] + value
    else:
        existing[key] = value
# existing["names"] is now ["FHIR", "HL7", "custom"]
```

### Exception design

```python
# Before: SystemExit from a library function bypasses test assertions
raise SystemExit(f"qa file not found: {path}")

# After: raise FileNotFoundError; let main() translate to exit code
raise FileNotFoundError(f"qa file not found: {path}")
```

## Related

- `docs/plans/2026-05-13-001-feat-add-test-suite-plan.md` — test suite plan that drove the testing practices above
