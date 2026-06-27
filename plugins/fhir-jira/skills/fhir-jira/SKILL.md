---
name: fhir-jira
description: Resolve a single HL7 FHIR JIRA ticket end-to-end. Use when the user invokes fhir-jira, asks to resolve one FHIR-NNNN ticket, or wants the FHIR JIRA workflow for a single ticket.
---

# FHIR JIRA

You have been asked to resolve a single HL7 FHIR JIRA ticket.

Treat the user's prompt as the equivalent of the Claude Code
`/fhir-jira <FHIR-NNNN> [optional notes]` command.

Follow the `fhir-jira-workflow` skill exactly. Do not skip steps. The ticket
may target the base FHIR specification, the FHIR Extensions Pack, or any FHIR
Implementation Guide. The workflow resolves the target repository automatically
using `scripts/resolve_repo.py` and `repo-map.json`.

Key flow:

1. Fetch the ticket to an external staging cache.
2. Resolve the target repository, default branch, and publisher command.
3. `cd` into that repo's local clone, asking the user if it does not exist.
4. Sync, branch, read context, and edit.
5. Run the correct publisher and confirm `qa.json` errors did not increase.
6. Generate the synopsis only after the publisher run reflects the final state.
7. Format the commit message and PR body with `scripts/format_messages.py`.
8. Commit, push, open a draft PR, and watch CI.

If the ticket disposition is non-trivial, stop and confirm the edit plan with
the user before writing. If CI fails, surface the failed step logs before
attempting a fix.
