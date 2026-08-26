---
description: Resolve multiple HL7 FHIR JIRA tickets, possibly spanning multiple repos. Produces one PR per repo touched.
argument-hint: <filter-id|FHIR-NNNN,FHIR-NNNN,...>
---

You have been asked to resolve a batch of HL7 FHIR JIRA tickets: **$ARGUMENTS**

Follow the `fhir-jira-workflow` skill, **batch procedure** section. The
batch may include tickets that target the base FHIR specification, the
Extensions Pack, and/or multiple FHIR IGs — each lives in a separate
GitHub repo. The skill groups tickets by target repo using
`scripts/resolve_repo.py --group ...` and then runs an independent
sub-batch flow per repo.

Key invariants:

- **One PR per repository touched.** Never combine PRs across repos.
- **One commit per ticket** within a repo's PR. Reviewers cherry-pick.
- Run the IG Publisher once per group (after all that group's edits) when
  the tickets touch disjoint files; run between tickets when they overlap.
- If `resolve_repo.py --group` returns any `unresolved` tickets, **stop
  and surface them to the user** before proceeding. Ask whether to skip
  or to add a mapping in `~/.config/fhir-jira-toolkit/repo-map.json`.
- For **FHIR Core** tickets, every modified resource must also get a
  "Changes since 6.0.0-ballotN" `stu-note` entry in its
  `<resource>-introduction.xml` (skill step 8a), committed with that ticket.
- Surface a final cross-repo summary listing every PR opened with its URL.

If the input looks like a number (e.g. `24101`), treat it as a JIRA filter
ID and resolve it to a ticket list. Otherwise treat it as an explicit list.

For any non-trivial ticket in any group, stop and confirm the edit plan
with the user before writing.
