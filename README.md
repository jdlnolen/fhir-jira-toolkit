# fhir-jira-toolkit

A plugin marketplace for Claude Code and Codex containing the `fhir-jira`
plugin — end-to-end tooling that takes HL7 FHIR JIRA tickets from "open" to
"draft PR with green CI" across the base FHIR specification, the FHIR
Extensions Pack, and FHIR Implementation Guides. Each spec lives in its own
GitHub repository; the plugin auto-resolves which repo a ticket targets.

## What you get

After installing the `fhir-jira` plugin from this marketplace:

### Claude Code slash commands

- **`/fhir-jira FHIR-NNNN`** — single-ticket workflow. Auto-resolves
  whether the ticket is against `HL7/fhir`, `HL7/fhir-extensions`, or an
  IG, and operates in the right repo.
- **`/fhir-jira-batch <filter-id|FHIR-NNNN,FHIR-NNNN,...>`** — batch
  workflow. Groups tickets by target repo and produces **one draft PR per repo**
  touched, with one commit per ticket inside each.

### Codex skill

- **`fhir-jira-workflow`** — the procedural body. Auto-triggers when you
  ask Codex or Claude to work on a FHIR JIRA ticket. In Codex, invoke it by
  asking naturally or by selecting the installed plugin/skill with `@`.

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

### Codex from GitHub

```bash
codex plugin marketplace add jdlnolen/fhir-jira-toolkit
codex plugin add fhir-jira@fhir-jira-toolkit
```

After installing, start a new Codex thread and ask it to use the FHIR JIRA
workflow:

```text
Use fhir-jira-workflow to resolve FHIR-12345.
```

### Claude Code from GitHub

In Claude Code:

```
/plugin marketplace add jdlnolen/fhir-jira-toolkit
/plugin install fhir-jira@fhir-jira-toolkit
```

Optionally override the default clone root if your HL7 repos aren't at
`~/dev/hl7/`:

```bash
mkdir -p ~/.config/fhir-jira-toolkit
echo '{"version": 1, "default_clone_root": "/your/path"}' \
  > ~/.config/fhir-jira-toolkit/repo-map.json
```

Then in a chat:

```
/fhir-jira FHIR-12345
```

### From a local directory

If you prefer a local install (or are developing the plugin):

```bash
git clone https://github.com/jdlnolen/fhir-jira-toolkit.git /path/to/fhir-jira-toolkit
```

For Codex:

```bash
codex plugin marketplace add /path/to/fhir-jira-toolkit
codex plugin add fhir-jira@fhir-jira-toolkit
```

For Claude Code:

```
/plugin marketplace add /path/to/fhir-jira-toolkit
/plugin install fhir-jira@fhir-jira-toolkit
```

See `INSTALL.md` for the full step-by-step including prerequisites
(`git`, `gh`, `python3`, IG Publisher) and per-repo QA baseline setup.

## How it works

1. The skill calls `fetch_ticket.py` to pull the ticket JSON from JIRA.
2. `resolve_repo.py` matches the ticket's `Specification` field (or, as
   a fallback, the URLs in its `Related URL` and description) against
   the repo map to determine which repo to operate in.
3. The agent `cd`s into that repo, syncs, branches, and reads the disposition.
4. The agent makes the edit. Non-trivial edits pause for user approval.
5. The IG Publisher runs locally; `parse_qa.py` confirms errors did not
   increase (per-repo baseline).
6. The agent writes the synopsis (only after the publisher passes).
7. `format_messages.py` produces the commit message and PR body.
8. The agent commits, pushes, opens a draft PR via `gh pr create --draft`,
   and watches CI.

For batch mode with tickets spanning multiple repos, this whole flow runs
once per repo, and a final summary lists every draft PR opened.

## HTML verification (optional)

After the publisher runs, the workflow can use the **Playwright MCP plugin**
to render the published HTML and verify that the intended change actually
appears in the output. This catches mechanical failures — wrong file edited,
publisher caching issues, stale build — that the QA error-count check alone
would miss.

### How it works

1. On the first run per session, while still on the default branch with a
   fresh publisher build, the workflow captures **baseline** screenshots and
   accessibility snapshots of the page(s) referenced by the ticket.
2. After the edit and publisher re-run on the feature branch, it captures
   the **current** output of the same pages.
3. Claude compares the two, checking whether the ticket's intended change
   is visible and no visual regressions were introduced.
4. If the check fails, Claude stops and asks whether to fix or override.

### Prerequisites

Install the Playwright/browser automation plugin for your agent runtime if you
want HTML verification. `fhir-jira` does not install browser tooling
automatically.

```
/plugin install playwright@claude-plugins-official
```

No other setup is needed.

If the Playwright plugin is **not installed**, the HTML verification steps
are skipped automatically and the rest of the workflow proceeds as usual.

### What gets verified

- The ticket's `Related URL` is mapped to the local publisher output path
  (see `references/fhir-authoring.md` for the mapping tables).
- Both a visual screenshot and a structured accessibility snapshot are
  captured for before/after comparison.
- Artifacts are stored under `$FHIR_JIRA_WORK_DIR/html-verify/` outside the
  target FHIR repository (baseline, current, and a verdict summary).

### Limitations

- **Advisory, not a hard gate.** The user can always override a failed
  check. The QA error-count check (`parse_qa.py`) remains the primary
  automated gate.
- **Same-session judgment.** The same agent instance that made the edit
  also judges the output. It catches mechanical errors reliably, but may
  miss semantic misinterpretations of the ticket.
- **Single-ticket only.** Batch mode (`/fhir-jira-batch`) does not yet
  include HTML verification; it will be added in a follow-up.

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

Verify by asking your agent in a chat: `Run resolve_repo.py --list`

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

## Compounding knowledge with compound-engineering

If you have planning, compounding, or knowledge-capture plugins installed, you
can use them alongside `fhir-jira` to capture and reuse what you learn while
resolving tickets. Keep their outputs outside the FHIR repository working tree
unless you explicitly intend to commit them to that project.

### Recommended workflow

1. **After resolving a tricky ticket**, capture the reusable learning in your
   personal or workspace knowledge location, not inside the target FHIR repo.

2. **Before starting a complex ticket**, create plans in a separate scratch
   workspace or `/tmp` location. Do not save plans under the FHIR repo.

3. **For domain knowledge** (FHIR patterns, HL7 conventions, publisher
   quirks), save insights to your configured personal knowledge store.

### Excluding plugin artifacts from git

Agent tools can create local workflow files that are useful to you but should
not be committed to FHIR repos:

| Directory | Created by | Contains |
|-----------|-----------|----------|
| `docs/plans/` | `/ce:plan`, `/kw:plan` | Implementation plans |
| `docs/solutions/` | `/ce:compound` | Documented solutions by category |
| `docs/knowledge/` | `/kw:compound` | Domain insights and learnings |
| `docs/brainstorms/` | `/ce:brainstorm`, `/kw:brainstorm` | Exploration notes |

The repository `.gitignore` already excludes these paths for this toolkit. For
target FHIR repositories, add them to `.git/info/exclude` (per-clone, never
committed) if your tools create them there:

```bash
cat >> .git/info/exclude <<'EOF'

# Compound-engineering and compound-knowledge plugin artifacts
docs/plans/
docs/solutions/
docs/knowledge/
docs/brainstorms/
EOF
```

Using `.git/info/exclude` rather than `.gitignore` keeps each FHIR project's
gitignore clean. These are personal developer tooling artifacts, not
project-level concerns.

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
├── .agents/
│   └── plugins/
│       └── marketplace.json                        ← Codex marketplace
├── .claude-plugin/
│   └── marketplace.json                            ← Claude Code marketplace
├── README.md
├── INSTALL.md
└── plugins/
    └── fhir-jira/                                  ← the plugin
        ├── .claude-plugin/
        │   └── plugin.json                         ← Claude Code manifest
        ├── .codex-plugin/
        │   └── plugin.json                         ← Codex manifest
        ├── commands/
        │   ├── fhir-jira.md                        ← Claude Code slash command
        │   └── fhir-jira-batch.md                  ← Claude Code slash command
        ├── hooks/
        │   └── check-update.py                     ← session-start update check
        └── skills/
            └── fhir-jira-workflow/
                ├── SKILL.md
                ├── repo-map.json
                ├── scripts/                        ← Python helpers
                └── references/                     ← skill reference docs
```
