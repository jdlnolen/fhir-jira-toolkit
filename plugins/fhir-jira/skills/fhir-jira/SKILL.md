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

The first action must be the shared workflow's required version currency
preflight. Do not fetch the ticket or inspect its target repository until the
running plugin is confirmed current, or the user explicitly accepts an
unverified version after a lookup failure.

Key flow:

1. Verify that the running plugin is the latest released version.
2. Fetch the ticket into a staging cache.
3. Resolve its target repository, default branch, and publisher command.
4. Enter the user's local clone, asking if it does not exist.
5. Sync, branch, read context, and edit.
6. Run the correct publisher. Review and stage every tracked file it changes
   with the intentional edits, even when the file is unexpected or belongs to
   another resource; exclude only untracked generated build artifacts. Then
   confirm the QA result did not regress.
7. Verify the requested result in the generated specification and record a
   ticket-specific published-output QA verdict.
8. Generate the synopsis only after the final publisher and semantic QA pass.
9. Format the commit and PR text with `scripts/format_messages.py`.
10. Commit, push, open a draft PR, and monitor CI.

For a non-trivial disposition, stop and confirm the edit plan before writing.
If CI fails, surface the failed step logs before attempting a fix.
