---
description: Resolve a single HL7 FHIR JIRA ticket end-to-end (resolve target repo, branch, edit, publish, commit, PR, CI).
argument-hint: <FHIR-NNNN> [optional notes]
---

You have been asked to resolve HL7 FHIR JIRA ticket: **$ARGUMENTS**

Follow the `fhir-jira-workflow` skill exactly. Do not skip steps. The ticket
may target the base FHIR specification, the FHIR Extensions Pack, or any
FHIR Implementation Guide — the skill resolves which automatically using
`scripts/resolve_repo.py` and the `repo-map.json` config.

The first action must be the shared workflow's required version currency
preflight. Do not fetch the ticket until the running plugin is confirmed
current, or the user explicitly accepts an unverified version after a lookup
failure.

Key flow:

1. Verify that the running plugin is the latest released version.
2. Fetch the ticket to a staging cache via the HL7 JIRA REST API.
3. Resolve the target repository, default branch, and publisher command.
4. `cd` into that repo's local clone (ask the user if it doesn't exist;
   never auto-clone).
5. Sync, branch, read context, edit.
6. Run the repository's publisher, stage every tracked file it changes with
   the intentional edits (including unexpected or cross-resource source
   updates), and confirm validation errors did not increase. Exclude only
   untracked generated build artifacts. FHIR Core uses its Gradle build log;
   IGs use `qa.json`.
7. Verify the requested result in the generated specification and record a
   ticket-specific published-output QA verdict.
8. Generate the synopsis **after** the publisher and semantic QA pass (must reflect final
   state, including any fix-ups).
9. Format the commit message and PR body via `scripts/format_messages.py`.
10. Commit, push, open the PR with `gh pr create --repo <slug>`, watch CI.

If the ticket disposition is non-trivial (anything beyond a typo, broken
link, or one-line clarification), **stop and confirm the edit plan with
the user before writing**. Surface the disposition text and proposed
change list first.

For **FHIR Core** tickets, every resource you modify must also get an entry
in its "Changes since 6.0.0-ballotN" note — the `stu-note` blockquote in
`source/<resource>/<resource>-introduction.xml` (skill step 8a). Do not skip
this; it is how the change surfaces on the published resource page.

If CI fails, fetch the failed step logs with `gh run view --log-failed`
and surface the failure to the user before attempting a fix.
