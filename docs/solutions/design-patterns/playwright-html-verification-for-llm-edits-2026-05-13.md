---
title: "Playwright HTML Verification for LLM-Generated Edits"
date: 2026-05-13
category: design-patterns
module: fhir-jira-workflow
problem_type: design_pattern
component: tooling
severity: low
applies_when:
  - "A Claude Code plugin workflow edits source files and runs a build/publisher step"
  - "The build succeeds but there is no check that the intended change appears in the rendered output"
  - "Playwright MCP plugin is available in the user's environment"
tags:
  - playwright
  - mcp
  - html-verification
  - visual-comparison
  - accessibility-snapshot
  - self-review-limitation
  - graceful-degradation
  - advisory-check
---

# Playwright HTML Verification for LLM-Generated Edits

## Context

When a Claude Code plugin workflow edits source files and runs a publisher
or build step, deterministic checks (exit codes, QA error counts) confirm
the tool succeeded — but they do not confirm the *intent* was achieved. A
FHIR spec edit might target the wrong source file, the publisher might
cache stale output, or a build-system quirk might silently drop the change.
These mechanical failures pass QA checks but produce incorrect rendered
HTML.

The gap: "publisher succeeded with no regressions" ≠ "the change actually
appears in the published output."

This learning documents the pattern for using Playwright MCP tools inside a
SKILL.md workflow to bridge that gap — and the critical limitations of an
LLM reviewing its own work.

## Guidance

### Use Playwright MCP in SKILL.md, not a Python script

Verification requires Claude's judgment (comparing rendered output against
a JIRA ticket's intent), not a deterministic algorithm. A Python script
would only handle file management, which SKILL.md instructions already
cover. Keep the Playwright tool calls as procedural instructions in
SKILL.md.

### Three-part capture-and-compare pattern

**1. Baseline capture (conditional/lazy)**

Piggyback on an existing "known-good" moment — don't add a separate build.
In the FHIR workflow, the QA baseline is captured conditionally on the
first run per session while on the default branch. HTML baseline capture
mirrors this exact timing:

```
While on the default branch with a fresh publisher build:
  browser_navigate → file://<absolute-path>/output/<page>.html
  browser_take_screenshot → filename: <absolute-path>/.jira-cache/html-verify/baseline/<page>.png
  browser_snapshot → filename: <absolute-path>/.jira-cache/html-verify/baseline/<page>.md
```

**2. Current-state capture (after edit and rebuild)**

```
After publisher runs on the feature branch:
  browser_navigate → file://<absolute-path>/output/<page>.html
  browser_take_screenshot → filename: <absolute-path>/.jira-cache/html-verify/current/<page>.png
  browser_snapshot → filename: <absolute-path>/.jira-cache/html-verify/current/<page>.md
```

**3. Advisory judgment (not a gate)**

Compare baseline and current snapshots against the ticket disposition.
Check that the intended change is visible and no visual regressions were
introduced. Write a verdict to `.jira-cache/html-verify/verdict.md`.

The user can always override a failed check. This is an advisory
verification, not a hard gate.

### Critical implementation details

1. **Use absolute paths for all Playwright filenames.** The MCP server's
   `--output-dir` is typically not configured to the repo root. Relative
   paths land in unpredictable locations.

2. **Explicitly read snapshot files back into context.** `browser_snapshot`
   with a `filename` parameter saves to disk but does *not* return content
   in the tool response. You must `Read` the file afterward to compare it.

3. **Document URL-to-local-path mappings in a reference file.** Different
   project types have different output directory structures. The FHIR
   toolkit needed a mapping table in `fhir-authoring.md` covering three
   repo types (Gradle build vs IG Publisher).

4. **Graceful degradation is mandatory.** If the Playwright MCP plugin is
   not installed, skip verification entirely with a note — don't block the
   workflow. The existing deterministic checks (QA error counts) remain the
   primary automated gate.

## Why This Matters

Without rendered-output verification, an LLM workflow can confidently
commit changes that look correct in the source but don't appear in the
published output. The failure modes are subtle: the right file was edited
but the publisher cached old output; the edit landed in the wrong section
of a complex XML file; the build system silently ignored a malformed
source change. These are exactly the mechanical errors that a visual/text
comparison catches.

The advisory framing matters because the same Claude instance that made the
edit also judges the output. This is structurally equivalent to
self-grading — if Claude misinterpreted the ticket, it will also
misinterpret the verification as passing. The check reliably catches
*mechanical* failures but should not be trusted for *semantic* correctness.

## When to Apply

- A Claude Code plugin workflow edits source files and runs a build step
  that produces HTML or other renderable output
- There is a "known-good" moment (baseline) available without an extra
  build step — e.g., the default branch already has a fresh build
- The Playwright MCP plugin is available (and the feature degrades
  gracefully when it isn't)
- Verification requires judgment (content comparison against intent) rather
  than a deterministic assertion (exit code, error count)

## Examples

### Before: QA-only verification

```
Step 9:  Run publisher             → exit code 0 ✓
Step 10: Parse QA delta            → errors <= baseline ✓
Step 11: Generate synopsis         → proceeds, but HTML may be wrong
```

### After: QA + HTML verification

```
Step 9:  Run publisher             → exit code 0 ✓
Step 10: Parse QA delta            → errors <= baseline ✓
Step 10a: Capture current HTML     → screenshot + accessibility snapshot saved
Step 10b: Verify HTML matches ticket → compare against baseline + disposition
  - Text check: intended change visible in accessibility snapshot? ✓
  - Visual check: no layout regressions in screenshot? ✓
  - Advisory verdict written to .jira-cache/html-verify/verdict.md
Step 11: Generate synopsis         → proceeds with verified output
```

### Self-review limitation — documented in SKILL.md

```markdown
**Limitations to be aware of:**

- This is the same Claude instance that made the edit. If you misinterpreted
  the ticket's intent, you may also misjudge the verification. Focus on
  mechanical checks (is the text present? did the right page change?) rather
  than semantic correctness judgments.
```

## Related

- `docs/solutions/best-practices/hardening-claude-code-python-plugins-2026-05-13.md` — sibling learning from same project; covers Python helper script patterns, shares `.jira-cache/` artifact convention
- `docs/plans/2026-05-13-002-feat-playwright-html-verification-plan.md` — implementation plan for this feature
- `plugins/fhir-jira/skills/fhir-jira-workflow/SKILL.md` steps 10a/10b — the implemented verification steps
- `plugins/fhir-jira/skills/fhir-jira-workflow/references/fhir-authoring.md` — URL-to-local-path mapping tables
