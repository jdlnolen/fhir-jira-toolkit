# fhir-jira-toolkit

A Claude Code marketplace containing the `fhir-jira` plugin — end-to-end
tooling that takes HL7 FHIR JIRA tickets from "open" to "PR with green CI"
across the base FHIR specification, the FHIR Extensions Pack, and FHIR
Implementation Guides. Each spec lives in its own GitHub repository; the
plugin auto-resolves which repo a ticket targets.

## What you get

After installing the `fhir-jira` plugin from this marketplace:

### Slash commands

- **`/fhir-jira FHIR-NNNN`** — single-ticket workflow. Auto-resolves
  whether the ticket is against `HL7/fhir`, `HL7/fhir-extensions`, or an
  IG, and operates in the right repo.
- **`/fhir-jira-batch <filter-id|FHIR-NNNN,FHIR-NNNN,...>`** — batch
  workflow. Groups tickets by target repo and produces **one PR per repo**
  touched, with one commit per ticket inside each.

### Skill

- **`fhir-jira-workflow`** — the procedural body. Auto-triggers when you
  ask Claude to work on a FHIR JIRA ticket even outside the slash commands.

### Helper scripts

- **`fetch_ticket.py`** — HL7 JIRA REST fetcher (no auth needed for public
  FHIR tickets), filter resolution, normalized summaries.
- **`resolve_repo.py`** — maps a ticket to its target GitHub repo via
  `Specification` field and `Related URL` patterns. Has a `--group` mode
  for batch resolution across repos.
- **`parse_qa.py`** — parses `output/qa.json` and computes a delta against
  a baseline. Exits non-zero on regression.
- **`format_messages.py`** — generates commit messages and PR bodies in
  the canonical format. Single-ticket and batch modes.

### Config

- **Default repo map** ships with FHIR core, Extensions Pack, US Core,
  IPS, and Genomics Reporting.
- **`~/.config/fhir-jira-toolkit/repo-map.json`** — user override
  (recommended for adding IGs and setting your clone root).
- **`./repo-map.local.json`** — project-local override (highest priority).

See `plugins/fhir-jira/skills/fhir-jira-workflow/references/repo-map.md`
for the schema and how to add IGs.

## Installation

See `INSTALL.md` for the full step-by-step. Quick version (assumes you
already have `git`, `gh`, `python3`, and the IG Publisher set up):

```bash
# 1. Unpack the marketplace somewhere stable
mkdir -p ~/.claude/marketplaces
unzip fhir-jira-toolkit.zip -d ~/.claude/marketplaces/

# 2. In Claude Code, register the local marketplace and install the plugin
/plugin marketplace add ~/.claude/marketplaces/fhir-jira-toolkit
/plugin install fhir-jira@fhir-jira-toolkit

# 3. (Optional) override the default clone root if your HL7 repos aren't at ~/dev/hl7/
mkdir -p ~/.config/fhir-jira-toolkit
echo '{"version": 1, "default_clone_root": "/your/path"}' \
  > ~/.config/fhir-jira-toolkit/repo-map.json
```

Then in a chat:

```
/fhir-jira FHIR-12345
```

## How it works

1. The skill calls `fetch_ticket.py` to pull the ticket JSON from JIRA.
2. `resolve_repo.py` matches the ticket's `Specification` field (or, as
   a fallback, the URLs in its `Related URL` and description) against
   the repo map to determine which repo to operate in.
3. Claude `cd`s into that repo, syncs, branches, and reads the disposition.
4. Claude makes the edit. Non-trivial edits pause for user approval.
5. The IG Publisher runs locally; `parse_qa.py` confirms errors did not
   increase (per-repo baseline).
6. Claude writes the synopsis (only after the publisher passes).
7. `format_messages.py` produces the commit message and PR body.
8. Claude commits, pushes, opens the PR via `gh`, and watches CI.

For batch mode with tickets spanning multiple repos, this whole flow runs
once per repo, and a final summary lists every PR opened.

## Synopsis discipline

Every commit and every PR section gets a 1-3 sentence synopsis describing
**what was actually done**, generated only after the IG Publisher run is
clean. The skill explicitly prohibits paraphrasing the disposition — the
disposition is what *should* happen; the synopsis is what *did* happen.

Batch PRs get one synopsis per ticket, with one commit per ticket — never
squashed — so reviewers can cherry-pick or revert individually.

## Adding an IG to the repo map

Edit `~/.config/fhir-jira-toolkit/repo-map.json`:

```json
{
  "version": 1,
  "specifications": [
    {
      "names": ["My IG"],
      "github": "HL7/fhir-my-ig",
      "default_branch": "main",
      "publisher": "./_updatePublisher.sh && ./_genonce.sh",
      "url_patterns": [
        "hl7\\.org/fhir/us/my-ig/",
        "build\\.fhir\\.org/ig/HL7/fhir-my-ig"
      ]
    }
  ]
}
```

Verify with:

```bash
~/.claude/marketplaces/fhir-jira-toolkit/plugins/fhir-jira/skills/fhir-jira-workflow/scripts/resolve_repo.py --list
```

Full schema: `plugins/fhir-jira/skills/fhir-jira-workflow/references/repo-map.md`.

## Customizing

- Add new commit-message trailers: edit `format_messages.py` `format_commit`.
- Change the QA tolerance (e.g., allow N new warnings): edit `parse_qa.py`
  `delta()` and the regression check.
- Support a different publisher (non-HL7): add a per-spec entry in the
  repo map with a custom `publisher` field.

After local edits, reload the plugin:

```
/reload-plugins
```

## Limits and known issues

- **Publisher is slow.** A FHIR-core run is 5-30 min; IGs are usually faster.
- **`qa.json` schema drift.** Multiple variants exist; the parser falls
  through several. If you hit a new variant, update `parse_qa.py`'s
  `counts()` function.
- **Filter access.** Some HL7 JIRA filters are private. If `fetch_ticket.py
  --filter <id>` returns an error, the filter probably needs auth.
- **Per-repo QA baselines.** Each repo needs its own `qa-baseline.json`,
  taken from the unmodified default branch. See `INSTALL.md` step 5.
- **Repo-map default branch values are advisory.** The skill verifies via
  `git remote show origin` before using them.

## Marketplace layout (for reference)

```
fhir-jira-toolkit/                                  ← marketplace root
├── .claude-plugin/
│   └── marketplace.json                            ← lists the plugin
├── README.md
├── INSTALL.md
└── plugins/
    └── fhir-jira/                                  ← the plugin
        ├── .claude-plugin/
        │   └── plugin.json
        ├── commands/
        │   ├── fhir-jira.md
        │   └── fhir-jira-batch.md
        └── skills/
            └── fhir-jira-workflow/
                ├── SKILL.md
                ├── repo-map.json
                ├── scripts/                        ← Python helpers
                └── references/                     ← skill reference docs
```
