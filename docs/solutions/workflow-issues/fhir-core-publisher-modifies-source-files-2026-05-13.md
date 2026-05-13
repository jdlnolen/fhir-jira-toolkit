---
title: "FHIR Core Gradle publisher modifies source files beyond direct edits"
date: 2026-05-13
category: workflow-issues
module: fhir-jira-workflow
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "Running ./gradlew publish on the FHIR Core repo (HL7/fhir)"
  - "Committing changes after a publisher run with explicit git add paths"
  - "Batch ticket processing where multiple resources are edited in one session"
tags:
  - fhir-core
  - gradle
  - publisher
  - git-staging
  - mapping-exceptions
  - spelling-dictionary
  - commit-hygiene
---

# FHIR Core Gradle publisher modifies source files beyond direct edits

## Context

The FHIR JIRA workflow enforces `git add` with explicit file paths (never
`-A`) to prevent committing build artifacts from `output/`, `temp/`,
`build/`, and `.gradle/`. This rule is correct but incomplete — the FHIR
Core Gradle publisher (`./gradlew publish`) also regenerates certain
**source files** as a side effect of building. These are not build
artifacts; they are canonical source-of-truth files that must be committed.

Without awareness of this behavior, the "explicit paths only" rule causes
these legitimate changes to be silently dropped from commits, leaving the
repository in an inconsistent state.

Discovered during a batch of FHIR Core ticket edits when `git status`
showed 8 modified `source/` files that were not directly edited.

## Guidance

After every `./gradlew publish` run, check `git status` for modified files
under `source/` that you did not directly edit. Stage them alongside your
intentional changes.

### Publisher-modified file patterns

| File pattern | Why it changes |
|---|---|
| `source/<resource>/<resource>-fivews-mapping-exceptions.xml` | FiveWs workflow mapping exceptions regenerated when resource definitions change |
| `source/<resource>/<resource>-request-mapping-exceptions.xml` | Request workflow mapping exceptions regenerated |
| `source/<resource>/<resource>-event-mapping-exceptions.xml` | Event workflow mapping exceptions regenerated |
| `source/spelling/add.txt` | Spelling dictionary updated with new terms from edits |

### The critical distinction

| Location | What it is | Commit? |
|---|---|---|
| `source/` | Source-of-truth files (including publisher-regenerated ones) | **Yes** |
| `output/`, `temp/`, `build/`, `.gradle/` | Build artifacts and caches | **Never** |

### Staging convention

```bash
# After ./gradlew publish, check for publisher-modified source files
git status

# Stage your direct edits
git add source/servicerequest/structuredefinition-ServiceRequest.xml

# Stage publisher-modified files too
git add source/servicerequest/servicerequest-request-mapping-exceptions.xml
git add source/spelling/add.txt

# Verify nothing from build_dirs is staged
git diff --cached --name-only | grep -E '^(output|temp|build|\.gradle)/' && echo "ERROR: build artifacts staged"
```

## Why This Matters

Mapping-exception files track which resource elements intentionally deviate
from standard workflow patterns (FiveWs, Request, Event). When these
updates are dropped from a commit:

- The next publisher run produces phantom diffs on the same files
- Other contributors see unexplained changes on unrelated branches
- QA may report false-positive mapping warnings because the exceptions
  list is stale relative to the resource definitions
- In batch mode, the problem compounds — each ticket's publisher run may
  touch mapping exceptions for different resources, and missing any of them
  leaves gaps

The spelling dictionary (`source/spelling/add.txt`) accumulates new terms
from resource definitions. Dropping updates causes the publisher to flag
known-good terms as spelling errors on future runs.

## When to Apply

- After every `./gradlew publish` run on FHIR Core, before staging and
  committing
- When reviewing a batch of FHIR Core ticket changes that span multiple
  resources (more resources touched = more mapping-exception files modified)
- When the commit includes changes to resource StructureDefinitions —
  these are the edits most likely to trigger mapping-exception regeneration
- **Does not apply to IGs or the Extensions Pack** — those use the IG
  Publisher (`_genonce.sh`), which writes only to `output/` and does not
  modify source files

## Examples

### Before: incomplete commit

```bash
# User edits ServiceRequest definition
git add source/servicerequest/structuredefinition-ServiceRequest.xml
git commit -m "fix(FHIR-45678): Update ServiceRequest.intent short description"
# Publisher-modified files silently left behind:
#   source/servicerequest/servicerequest-request-mapping-exceptions.xml
#   source/spelling/add.txt
```

### After: complete commit

```bash
# User edits ServiceRequest definition, then checks git status
git status
# Sees both direct edit AND publisher-modified files

git add source/servicerequest/structuredefinition-ServiceRequest.xml
git add source/servicerequest/servicerequest-request-mapping-exceptions.xml
git add source/spelling/add.txt
git commit -m "fix(FHIR-45678): Update ServiceRequest.intent short description"
# Complete commit — no phantom diffs for the next contributor
```

## Related

- `plugins/fhir-jira/skills/fhir-jira-workflow/SKILL.md` step 13 — commit instructions updated with this guidance
- `plugins/fhir-jira/skills/fhir-jira-workflow/references/fhir-authoring.md` — "Publisher-modified source files" section added
- `docs/solutions/best-practices/hardening-claude-code-python-plugins-2026-05-13.md` — sibling learning covering Python helper script conventions in the same project
