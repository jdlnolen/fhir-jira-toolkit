---
name: fhir-jira-batch
description: Resolve multiple HL7 FHIR JIRA tickets, possibly spanning multiple repos. Use when the user invokes fhir-jira-batch, provides a FHIR JIRA filter ID, or asks to process multiple FHIR tickets.
---

# FHIR JIRA Batch

You have been asked to resolve a batch of HL7 FHIR JIRA tickets.

Treat the user's prompt as the equivalent of the Claude Code
`/fhir-jira-batch <filter-id|FHIR-NNNN,FHIR-NNNN,...>` command.

Follow the `fhir-jira-workflow` skill's batch procedure exactly. The batch may
include tickets that target the base FHIR specification, the FHIR Extensions
Pack, and/or multiple FHIR Implementation Guides. The workflow groups tickets
by target repository using `scripts/resolve_repo.py --group ...`, then runs an
independent sub-batch flow for each repository.

Key invariants:

- One draft PR per repository touched. Never combine PRs across repos.
- One commit per ticket within a repo's PR. Reviewers cherry-pick.
- Run the publisher once per group after all edits when tickets touch disjoint
  files; run between tickets when edits overlap.
- If `resolve_repo.py --group` returns unresolved tickets, stop and surface
  them to the user before proceeding.
- Surface a final cross-repo summary listing every PR opened with its URL.

If the input looks like a number, treat it as a JIRA filter ID. Otherwise,
treat it as an explicit ticket list. For any non-trivial ticket in any group,
stop and confirm the edit plan with the user before writing.
