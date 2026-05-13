# Commit message and PR body templates

These are what `format_messages.py` produces. Pasting them here so the
formatting is reviewable without reading the script.

## Single-ticket commit message

```
FHIR-NNNN: <ticket summary, lightly cleaned, <= 72 chars total subject>

<1-3 sentence synopsis of what was actually done. Wrapped at 72 chars.
Spec-author voice. Diffs against the disposition — calls out any
divergence or judgment call.>

Disposition: Persuasive | Persuasive with Modification | ...
Ticket: https://jira.hl7.org/browse/FHIR-NNNN
```

Hard rules:
- Subject line `<= 72` chars including the `FHIR-NNNN: ` prefix
- Body lines wrapped at 72
- Trailers (`Disposition:`, `Ticket:`) at the bottom, no blank line between them

The Disposition trailer is metadata for `git log` searches and historical
audit — it's deliberately kept in the commit message but not echoed in
the PR body.

## Single-ticket PR body

```markdown
Resolves [FHIR-NNNN](https://jira.hl7.org/browse/FHIR-NNNN): <summary>

## What changed
<2-4 sentence synopsis>

## Files touched
- `source/foo/foo.xml`
- `source/foo/foo-notes.md`

## Publisher QA

| metric | baseline | current | delta |
|---|---:|---:|---:|
| errors | 0 | 0 | 0 |
| warnings | 142 | 141 | -1 |
| info | 89 | 89 | 0 |
| broken_links | 0 | 0 | 0 |
```

The PR body intentionally omits the disposition text and the ticket's
resolution category. The ticket link in the "Resolves" line is enough
context — reviewers who want the disposition can click through.

## Batch PR body

```markdown
This PR addresses N ticket(s).

## Tickets
- [FHIR-1234](https://jira.hl7.org/browse/FHIR-1234): <summary>
- [FHIR-1235](https://jira.hl7.org/browse/FHIR-1235): <summary>

## FHIR-1234: <summary>

<synopsis>

**Files:** `source/...`, `source/...`

[Ticket](https://jira.hl7.org/browse/FHIR-1234)

---

## FHIR-1235: <summary>

<synopsis>

**Files:** `source/...`

[Ticket](https://jira.hl7.org/browse/FHIR-1235)

---

## Publisher QA

| metric | baseline | current | delta |
|---|---:|---:|---:|
| errors | 0 | 0 | 0 |
| warnings | 142 | 141 | -1 |
| info | 89 | 89 | 0 |
| broken_links | 0 | 0 | 0 |
```

## On synopsis quality

A good synopsis:

- Names the file(s) or section(s) touched
- States the substantive change in one declarative sentence
- Calls out anything that diverges from the disposition

Avoid:

- Pasting the disposition back as the synopsis
- Vague verbs like "fixed", "updated", "improved" without an object
- Process talk: "ran the publisher", "rebased the branch"

### Examples

Good: "Added a new example to `source/observation/observation-examples.md`
showing a Quantity with an SI-derived unit, per the disposition. Also
updated the cross-reference in `observation-notes.md` so it points to
the new example."

Bad: "Fixed an issue with examples per the disposition."
