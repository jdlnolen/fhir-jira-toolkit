---
name: fhir-jira-batch
description: Resolve multiple HL7 FHIR JIRA tickets, possibly spanning multiple repos. Use when the user invokes fhir-jira-batch, provides a FHIR JIRA filter ID, or asks to process multiple FHIR tickets.
---

# FHIR JIRA Batch

Resolve the ticket batch supplied by the user by following the
`fhir-jira-workflow` skill's batch procedure exactly. In Claude Code, the
filter ID or ticket-list arguments are provided here: `$ARGUMENTS`. In Codex,
use the filter ID or ticket list from the user's request.

The batch may include tickets for FHIR Core, the FHIR Extensions Pack, and
multiple Implementation Guides. Group tickets by target repository with
`scripts/resolve_repo.py --group ...`, then run an independent sub-batch for
each repository.

Keep these invariants:

- Open one draft PR per repository touched.
- Create one commit per ticket within each repository PR.
- Run the publisher once after disjoint edits, or between overlapping edits.
- After a clean publisher result, verify each ticket separately in the
  generated specification and record one published-output QA verdict per
  ticket. A group-level spot check is not sufficient.
- Stop and surface any unresolved tickets before proceeding.
- Finish with a cross-repository summary of every PR opened.

Treat a numeric input as a JIRA filter ID; otherwise treat the input as an
explicit ticket list. Confirm the edit plan before writing any non-trivial
ticket change.
