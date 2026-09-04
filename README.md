# fhir-jira-toolkit

A dual-host plugin marketplace for Codex and Claude Code. Its `fhir-jira`
plugin takes HL7 FHIR JIRA tickets from "open" to "draft PR with green CI"
across FHIR Core, the FHIR Extensions Pack, and FHIR Implementation Guides.
Each specification lives in its own GitHub repository; the plugin resolves
the target repository automatically.

## What you get

After installing the `fhir-jira` plugin from this marketplace:

### Claude Code slash commands

- **`/fhir-jira FHIR-NNNN`** — single-ticket workflow. Auto-resolves
  whether the ticket is against `HL7/fhir`, `HL7/fhir-extensions`, or an
  IG, and operates in the right repo.
- **`/fhir-jira-batch <filter-id|FHIR-NNNN,FHIR-NNNN,...>`** — batch
  workflow. Groups tickets by target repo and produces **one draft PR per repo**
  touched, with one commit per ticket inside each.

### Codex skills

- **`fhir-jira`** — the single-ticket entrypoint.
- **`fhir-jira-batch`** — the multi-ticket/filter entrypoint.
- **`fhir-jira-workflow`** — the shared procedural body. It can also
  auto-trigger when you ask Codex or Claude Code to work on a FHIR JIRA ticket.

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

Start a new Codex task, then ask naturally or invoke the installed skill:

```text
Use fhir-jira to resolve FHIR-12345.
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
3. The agent enters that repo, syncs, branches, and reads the disposition.
4. The agent makes the edit. For FHIR Core, it also records the ticket under
   the JIRA `Change Impact` category in each affected resource's Note to
   Balloters and audits the note's overview and module-page links. Non-trivial
   edits pause for user approval.
5. The repository's publisher runs locally; `parse_qa.py` confirms errors did
   not increase (FHIR Core uses its Gradle log; IGs use `qa.json`).
6. The agent verifies each ticket in the generated specification and records a
   published-output QA verdict.
7. The agent writes the synopsis only after both gates pass.
8. `format_messages.py` produces the commit message and PR body.
9. The agent commits, pushes, opens a draft PR via `gh`, and watches CI.

For batch mode with tickets spanning multiple repos, this whole flow runs
once per repo, and a final summary lists every PR opened.

## Published-output QA (required)

After publisher validation succeeds, the workflow verifies every ticket
against the generated specification. This is a separate semantic gate: a clean
error count does not prove that the requested change reached the right page,
uses the right code or reference, or is appropriate in its published context.

### How it works

1. The agent converts each ticket disposition into an expected-result
   checklist.
2. It locates the generated artifact under `publish/` for FHIR Core or
   `output/` for the Extensions Pack and IGs.
3. It checks the requested content or behavior, its placement and context,
   removed content, and relevant links or FHIR references.
4. It records one `PASS` or `FAIL` verdict per ticket under
   `.jira-cache/published-qa/`.
5. A failure returns to editing and publisher validation unless the user
   explicitly accepts the documented risk.

### Prerequisites

Browser automation adds rendered-page, visual, and link evidence when the
active host provides it. For Claude Code, install the separate Playwright
plugin from Anthropic's official marketplace:

```
/plugin install playwright@claude-plugins-official
```

If compatible browser tools are unavailable, the agent reads and searches the
generated HTML/XML/JSON directly. The semantic QA step is not skipped.

### What gets verified

- The ticket's `Related URL` is mapped to the local publisher output path
  (see `references/fhir-authoring.md` for the mapping tables).
- The requested text, code, value, reference, or behavior is present.
- The result appears on the correct page and is appropriate in context.
- Replaced content is absent and relevant links/references resolve.
- For FHIR Core, the resource's Note to Balloters contains the ticket exactly
  once under its JIRA `Change Impact` category; its overview covers the
  affected surface and evidence-backed module-page links resolve.
- Written verdicts are stored in `.jira-cache/published-qa/`; screenshots and
  accessibility snapshots are optional supporting evidence.

### Limitations

- **Same-session judgment.** The same agent instance that made the edit
  also judges the output. It catches mechanical errors reliably, but may
  miss semantic misinterpretations of the ticket.
- **Explicit override only.** A failed verdict blocks synopsis and PR creation
  unless the user reviews the evidence and accepts the risk.

## Synopsis discipline

Every commit and every PR section gets a 1-3 sentence synopsis describing
**what was actually done**, generated only after the IG Publisher run is
clean. The skill explicitly prohibits paraphrasing the disposition — the
disposition is what *should* happen; the synopsis is what *did* happen.

Batch PRs get one synopsis per ticket, with one commit per ticket — never
squashed — so reviewers can cherry-pick or revert individually. For FHIR Core,
that ticket commit also includes its categorized resource-page ballot impact.

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

Verify by asking Codex or Claude Code: `Run resolve_repo.py --list`

Full schema: `plugins/fhir-jira/skills/fhir-jira-workflow/references/repo-map.md`.

## Customizing

- Add new commit-message trailers: edit `format_messages.py` `format_commit`.
- Change the QA tolerance (e.g., allow N new warnings): edit `parse_qa.py`
  `delta()` and the regression check.
- Support a different publisher (non-HL7): add a per-spec entry in the
  repo map with a custom `publisher` field.

After local edits, refresh the host. Start a new Codex task after reinstalling;
in Claude Code run:

```
/reload-plugins
```

## Compounding knowledge with compound-engineering

If you have the [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin)
and/or [compound-knowledge](https://github.com/EveryInc/compound-knowledge-plugin)
plugins installed, you can use them alongside `fhir-jira` to capture and
reuse what you learn while resolving tickets.

### Recommended workflow

1. **After resolving a tricky ticket**, run `/ce:compound` to document the
   solution. The plugin saves it to `docs/solutions/` with searchable
   frontmatter (category, tags, severity). Next time a similar ticket
   comes up, the learnings-researcher agent finds it automatically.

2. **Before starting a complex ticket**, run `/ce:plan` to structure your
   approach. The planner searches `docs/solutions/` for past solutions
   that apply — so knowledge from earlier tickets flows forward without
   you having to remember it.

3. **For domain knowledge** (FHIR patterns, HL7 conventions, publisher
   quirks), run `/kw:compound` to save insights to `docs/knowledge/`.
   These are searched by `/kw:plan` and the knowledge-base-researcher
   agent in future sessions.

### Excluding plugin artifacts from git

The compound plugins create local workflow files that are useful to you
but shouldn't be committed to the repo:

| Directory | Created by | Contains |
|-----------|-----------|----------|
| `docs/plans/` | `/ce:plan`, `/kw:plan` | Implementation plans |
| `docs/solutions/` | `/ce:compound` | Documented solutions by category |
| `docs/knowledge/` | `/kw:compound` | Domain insights and learnings |
| `docs/brainstorms/` | `/ce:brainstorm`, `/kw:brainstorm` | Exploration notes |

Add these to your `.git/info/exclude` (per-clone, never committed):

```bash
cat >> .git/info/exclude <<'EOF'

# Compound-engineering and compound-knowledge plugin artifacts
docs/plans/
docs/solutions/
docs/knowledge/
docs/brainstorms/
EOF
```

Using `.git/info/exclude` rather than `.gitignore` keeps the project's
gitignore clean — these are personal developer tooling artifacts, not
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
├── .agents/plugins/
│   └── marketplace.json                            ← Codex marketplace
├── .claude-plugin/
│   └── marketplace.json                            ← Claude Code marketplace
├── README.md
├── INSTALL.md
└── plugins/
    └── fhir-jira/                                  ← the plugin
        ├── .claude-plugin/
        │   └── plugin.json                          ← Claude Code manifest
        ├── .codex-plugin/
        │   └── plugin.json                          ← Codex manifest
        ├── commands/
        │   ├── fhir-jira.md
        │   └── fhir-jira-batch.md
        ├── hooks/
        │   └── check-update.py                     ← session-start update check
        └── skills/
            ├── fhir-jira/                           ← Codex entrypoint
            ├── fhir-jira-batch/                     ← Codex batch entrypoint
            └── fhir-jira-workflow/
                ├── SKILL.md
                ├── repo-map.json
                ├── scripts/                        ← Python helpers
                └── references/                     ← skill reference docs
```
