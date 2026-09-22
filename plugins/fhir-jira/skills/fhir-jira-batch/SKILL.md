---
name: fhir-jira-batch
description: Resolve multiple HL7 FHIR JIRA tickets, possibly spanning multiple repos. Use when the user invokes fhir-jira-batch, provides a FHIR JIRA filter ID, or asks to process multiple FHIR tickets.
---

# FHIR JIRA Batch

Resolve the ticket batch supplied by the user by following the
`fhir-jira-workflow` skill's batch procedure exactly. In Claude Code, the
filter ID or ticket-list arguments are provided here: `$ARGUMENTS`. In Codex,
use the filter ID or ticket list from the user's request.

The first action must be the shared workflow's required version currency
preflight. Do not fetch the filter or any ticket until the running plugin is
confirmed current, or the user explicitly accepts an unverified version after
a lookup failure.

The batch may include tickets for FHIR Core, the FHIR Extensions Pack, and
multiple Implementation Guides. Group tickets by target repository with
`scripts/resolve_repo.py --group ...`, then run an independent sub-batch for
each repository.

Keep these invariants:

- Open one draft PR per repository touched.
- Before editing any FHIR Core resource, ask the user to confirm the exact
  release-note heading or label unless the current request already supplies
  it. Ask once when one label applies to the whole batch; otherwise request a
  resource-to-label mapping. Do not infer the label from JIRA Change Impact.
- Create one commit per ticket within each repository PR.
- Run the publisher once after disjoint edits, or between overlapping edits.
- After every publisher run, stage every tracked file it changes with the
  intentional edits, including unexpected or cross-resource source updates.
  Never restore or omit one to narrow the diff; exclude only untracked
  generated artifacts in configured build directories.
- After a clean publisher result, verify each ticket separately in the
  generated specification and record one published-output QA verdict per
  ticket. A group-level spot check is not sufficient.
- Stop and surface any unresolved tickets before proceeding.
- Finish with a cross-repository summary of every PR opened.

Treat a numeric input as a JIRA filter ID; otherwise treat the input as an
explicit ticket list. Confirm the edit plan before writing any non-trivial
ticket change.
