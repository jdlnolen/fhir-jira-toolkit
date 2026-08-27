---
description: Resolve a single HL7 FHIR JIRA ticket end-to-end (resolve target repo, branch, edit, publish, commit, PR, CI).
argument-hint: <FHIR-NNNN> [optional notes]
---

You have been asked to resolve HL7 FHIR JIRA ticket: **$ARGUMENTS**

Follow the `fhir-jira-workflow` skill exactly. Do not skip steps. The ticket
may target the base FHIR specification, the FHIR Extensions Pack, or any
FHIR Implementation Guide — the skill resolves which automatically using
`scripts/resolve_repo.py` and the `repo-map.json` config.

Key flow:

1. Fetch the ticket to a staging cache via the HL7 JIRA REST API.
2. Resolve the target repository, default branch, and publisher command.
3. `cd` into that repo's local clone (ask the user if it doesn't exist;
   never auto-clone).
4. Sync, branch, read context, edit.
5. Run the repository's publisher and confirm validation errors did not
   increase (FHIR Core uses its Gradle build log; IGs use `qa.json`).
6. Verify the requested result in the generated specification and record a
   ticket-specific published-output QA verdict.
7. Generate the synopsis **after** the publisher and semantic QA pass (must reflect final
   state, including any fix-ups).
8. Format the commit message and PR body via `scripts/format_messages.py`.
9. Commit, push, open the PR with `gh pr create --repo <slug>`, watch CI.

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
