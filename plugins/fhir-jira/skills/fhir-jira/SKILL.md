---
name: fhir-jira
description: Resolve a single HL7 FHIR JIRA ticket end-to-end. Use when the user invokes fhir-jira, asks to resolve one FHIR-NNNN ticket, or wants the FHIR JIRA workflow for a single ticket.
---

# FHIR JIRA

Resolve the single HL7 FHIR JIRA ticket supplied by the user. In Claude Code,
the slash-command arguments are provided here: `$ARGUMENTS`. In Codex, use the
ticket key and notes from the user's request.

Follow the `fhir-jira-workflow` skill exactly. Do not skip steps. The ticket
may target FHIR Core, the FHIR Extensions Pack, or an Implementation Guide.
The workflow resolves the target repository with `scripts/resolve_repo.py`
and the shipped `repo-map.json`.

Key flow:

1. Fetch the ticket into a staging cache.
2. Resolve its target repository, default branch, and publisher command.
3. Enter the user's local clone, asking if it does not exist.
4. Sync, branch, read context, and edit.
5. Run the correct publisher and confirm the QA result did not regress.
6. Verify the requested result in the generated specification and record a
   ticket-specific published-output QA verdict.
7. Generate the synopsis only after the final publisher and semantic QA pass.
8. Format the commit and PR text with `scripts/format_messages.py`.
9. Commit, push, open a draft PR, and monitor CI.

For a non-trivial disposition, stop and confirm the edit plan before writing.
If CI fails, surface the failed step logs before attempting a fix.
