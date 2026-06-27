# Install instructions

Codex and Claude Code both install plugins through marketplaces. This bundle
ships one plugin, `fhir-jira`, with both marketplace formats:

- Codex reads `.agents/plugins/marketplace.json` and
  `plugins/fhir-jira/.codex-plugin/plugin.json`.
- Claude Code reads `.claude-plugin/marketplace.json` and
  `plugins/fhir-jira/.claude-plugin/plugin.json`.

## Step 0 — Prerequisites

### Codex

Install the Codex CLI/app and confirm the CLI is available:

```bash
codex --version
```

You can add the marketplace from GitHub or from a local checkout. After
installing or updating a plugin, start a new Codex thread so the skill is
loaded into the new session.

### Claude Code

Recent enough that `/plugin marketplace` is a recognized command:

```bash
claude --version
# If too old, update via your install method:
#   npm:    npm install -g @anthropic-ai/claude-code
#   brew:   brew upgrade claude
```

### Python 3.9+

```bash
python3 --version    # need 3.9 or newer
```

Scripts use only the standard library — no `pip install` needed.

### git

```bash
git --version
```

If missing: `brew install git` (macOS), `sudo apt install git` (Debian/Ubuntu), etc.

### GitHub CLI (`gh`)

Install:

```bash
# macOS
brew install gh

# Debian/Ubuntu (official repo — community packages are broken on current GitHub APIs)
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
&& sudo mkdir -p -m 755 /etc/apt/keyrings \
&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
   | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update && sudo apt install gh -y

# Fedora/RHEL
sudo dnf install gh

# Windows (PowerShell)
winget install --id GitHub.cli
```

Authenticate:

```bash
gh auth login
# 1. GitHub.com
# 2. HTTPS as preferred Git protocol
# 3. Yes, authenticate Git operations
# 4. Login with a web browser, complete the flow
```

Verify scopes include `repo`, `workflow`, and `read:org`:

```bash
gh auth status
# Look for: Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

If `repo` or `workflow` are missing:

```bash
gh auth refresh -s repo,workflow,read:org
```

### Push access to HL7 repos

```bash
cd ~/dev/hl7/fhir   # or wherever your clone is
git push --dry-run origin master 2>&1 | head -3
# "Everything up-to-date" or "would push" → you have commit rights
# "Permission denied" → you need to work via a fork (see README)
```

### IG Publisher

### Build tooling per repo

Each repo has its own build system; you only need the tooling for the
specs you'll actually work on.

**FHIR Core (`HL7/fhir`) — Gradle build.** Verify in the repo:

```bash
cd ~/dev/hl7/fhir
ls gradlew                    # Gradle wrapper
java -version                  # 17+ recommended for current FHIR Core
./gradlew --version            # smoke-check the build works
```

**Extensions Pack and IGs — HL7 IG Publisher.** Verify in any IG repo:

```bash
cd ~/dev/hl7/US-Core         # or any IG
ls _genonce.sh _updatePublisher.sh   # at least one should exist
java -version                         # 11+ required by the IG Publisher
```

If the IG Publisher isn't set up for an IG, see HL7's docs:
https://confluence.hl7.org/display/FHIR/IG+Publisher+Documentation

### Local clones of HL7 repos

The plugin doesn't auto-clone. At minimum:

```bash
mkdir -p ~/dev/hl7
cd ~/dev/hl7
gh repo clone HL7/fhir              # only if you'll work on FHIR core
gh repo clone HL7/fhir-extensions   # only if you'll work on the Extensions Pack
gh repo clone HL7/US-Core           # any IG you'll work on
# ... etc
```

You only need clones for repos you'll actually work in.

---

## Step 1 — Add the marketplace

### Codex from GitHub

```bash
codex plugin marketplace add jdlnolen/fhir-jira-toolkit
```

Codex supports GitHub shorthand (`owner/repo`) for marketplace sources. This
repository includes `.agents/plugins/marketplace.json`, so no manual
`config.toml` edits are needed.

Confirm Codex sees the marketplace:

```bash
codex plugin marketplace list
```

### Codex from a local clone

If you prefer a local install, or GitHub is unreachable:

```bash
git clone https://github.com/jdlnolen/fhir-jira-toolkit.git /path/to/fhir-jira-toolkit
codex plugin marketplace add /path/to/fhir-jira-toolkit
```

### Claude Code from GitHub

Open Claude Code. In any conversation, run:

```
/plugin marketplace add jdlnolen/fhir-jira-toolkit
```

Expected output:

```
✓ Fetching marketplace registry...
✓ Adding fhir-jira-toolkit marketplace

Available plugins:
  • fhir-jira

Run /plugin install <name> to install
```

### Claude Code from a local clone

If you prefer a local install, or GitHub is unreachable:

```bash
git clone https://github.com/jdlnolen/fhir-jira-toolkit.git /path/to/fhir-jira-toolkit
```

Then in Claude Code:

```
/plugin marketplace add /path/to/fhir-jira-toolkit
```

### Troubleshooting

- **`unknown command`** — your Claude Code is too old. Update with
  `npm install -g @anthropic-ai/claude-code` (or your install method)
  and restart your terminal.
- **`marketplace.json not found`** — the path or repo is wrong. For Codex,
  check that `.agents/plugins/marketplace.json` exists. For Claude Code,
  check that `.claude-plugin/marketplace.json` exists at the root.
- **`invalid marketplace.json`** — the file is malformed. Check for
  syntax errors.

To confirm:

```
/plugin marketplace list
```

You should see `fhir-jira-toolkit` listed.

---

## Step 2 — Install the plugin from the marketplace

### Codex

```bash
codex plugin add fhir-jira@fhir-jira-toolkit
```

You can also open the Codex plugin directory from the CLI (`codex`, then
`/plugins`) or from the Codex app, select the `fhir-jira-toolkit`
marketplace, and install `fhir-jira`.

Start a new thread before using the plugin:

```text
Use fhir-jira-workflow to resolve FHIR-12345.
```

### Claude Code

```
/plugin install fhir-jira@fhir-jira-toolkit
```

The `@` syntax is `<plugin-name>@<marketplace-name>` — both come from the
manifests you registered.

Expected output:

```
✓ Installing fhir-jira from fhir-jira-toolkit
✓ Plugin installed: fhir-jira
```

To confirm:

```
/plugin
```

This opens the plugin browser. Under **Installed**, `fhir-jira` should
appear and be enabled.

---

## Step 3 — Verify the plugin is available

### Codex

Start a new Codex thread and ask for the installed skill:

```text
Use the fhir-jira-workflow skill to run resolve_repo.py --list.
```

If Codex does not pick up the plugin, restart Codex or run
`codex plugin marketplace upgrade fhir-jira-toolkit`, then start another new
thread.

### Claude Code

In a chat, type `/` and look for autocomplete suggestions. You should see:

- `/fhir-jira`
- `/fhir-jira-batch`

If they don't appear:

1. Type the full name (`/fhir-jira` and press space) — sometimes
   autocomplete is lazy. The command name should turn blue once recognized.
2. Run `/reload-plugins` — picks up changes without restarting.
3. Restart Claude Code — plugin discovery happens at session start.

---

## Step 4 — Configure your clone root (one-time)

The shipped repo map assumes HL7 clones live at `~/dev/hl7/<repo-name>`.
If yours don't, set this once:

```bash
mkdir -p ~/.config/fhir-jira-toolkit
cat > ~/.config/fhir-jira-toolkit/repo-map.json <<EOF
{
  "version": 1,
  "default_clone_root": "/your/actual/path/to/hl7-clones"
}
EOF
```

If `~/dev/hl7/` works for you, skip this step.

---

## Step 5 — Verify repo resolution points where you think

Ask Codex or Claude to verify in a chat:

```
Run resolve_repo.py --list and show me the results
```

Or run the script directly from the installed marketplace checkout:

```bash
PLUGIN_ROOT=/path/to/fhir-jira-toolkit/plugins/fhir-jira
python3 "$PLUGIN_ROOT/skills/fhir-jira-workflow/scripts/resolve_repo.py" --list
```

You should see the five shipped specs with their resolved local paths.
Sanity-check that each `local:` path matches where your clone actually
lives. Any path that's wrong is a path you'll need to fix (either by
moving the clone, symlinking, or adding a per-spec `local_path` override
in your config — see `plugins/fhir-jira/skills/fhir-jira-workflow/references/repo-map.md`).

For specs whose clones you don't have yet, that's fine — the plugin will
ask before doing anything in those repos.

---

## Step 6 — Capture per-repo QA baselines (one-time per repo)

The skill compares each publisher run against a `qa-baseline.json` for
that repo. Store baselines outside the FHIR repo working tree. Establish the
baseline on a clean default branch **before** any ticket work in that repo:

```bash
# FHIR Core
cd ~/dev/hl7/fhir
git checkout master && git pull
./gradlew publish
FHIR_JIRA_WORK_DIR=/tmp/fhir-jira-work/HL7-fhir
mkdir -p "$FHIR_JIRA_WORK_DIR"
cp output/qa.json "$FHIR_JIRA_WORK_DIR/qa-baseline.json"   # adjust path if Gradle writes elsewhere

# Extensions Pack or any IG
cd ~/dev/hl7/US-Core              # or whichever
git checkout master && git pull   # or main, per the repo
./_updatePublisher.sh && ./_genonce.sh
FHIR_JIRA_WORK_DIR=/tmp/fhir-jira-work/HL7-US-Core
mkdir -p "$FHIR_JIRA_WORK_DIR"
cp output/qa.json "$FHIR_JIRA_WORK_DIR/qa-baseline.json"
```

If the FHIR Core Gradle build writes its QA report somewhere other than
`output/qa.json` (it may be `build/publish/qa.json` or similar), adjust
the `cp` source path accordingly. Run the build once and `find . -name qa.json`
to locate it on first setup.

Repeat in every repo you'll touch. Each repo gets its own baseline.

As a backstop, add common agent artifact paths to each FHIR clone's
`.git/info/exclude` if your tools ever create them there:

```bash
cat >> .git/info/exclude <<'EOF'
.jira-cache/
.codex/
.claude/
docs/plans/
docs/solutions/
docs/knowledge/
docs/brainstorms/
EOF
```

If you skip baseline capture, the QA delta block in your PR bodies will show
absolute counts only ("warnings: 142") instead of deltas. Not harmful,
just less informative.

---

## Step 7 — Smoke test against a real ticket

Pick a low-stakes, already-resolved FHIR ticket.

In Codex:

```text
Use fhir-jira-workflow to resolve FHIR-XXXXX.
```

In Claude Code:

```
/fhir-jira FHIR-XXXXX
```

Watch what happens:

1. **Ticket fetch.** Normalized summary prints — verify `Specification`
   looks right.
2. **Repo resolution.** Output shows `github`, `local_path`, etc. — verify
   these match expectations.
3. **Plan confirmation.** For non-trivial tickets, the plugin pauses for
   your approval. This is the right time to bail with "stop, I just
   wanted to verify the plumbing" if you don't actually want to make a PR.
4. **Branch, edit, publisher.** Slow part (5–30 min for FHIR core).
5. **Commit and PR.** Verify the PR is a draft and the PR body has the "What changed" synopsis,
   the "Files touched" list, and the QA delta table. The commit message
   (not the PR body) carries the `Disposition:` and `Ticket:` trailers.

If anything goes wrong, the script outputs live under `$FHIR_JIRA_WORK_DIR`
outside the FHIR repo — that's your debugging trail.

---

## Updating the plugin

### Codex

If you installed from GitHub, refresh the marketplace and reinstall the plugin:

```bash
codex plugin marketplace upgrade fhir-jira-toolkit
codex plugin add fhir-jira@fhir-jira-toolkit
```

Start a new Codex thread after reinstalling.

### Claude Code

If you installed from GitHub, Claude Code pulls the latest version
automatically when the marketplace is refreshed. To force a refresh:

```
/reload-plugins
```

If you installed from a local clone, pull the latest and reload:

```bash
cd /path/to/fhir-jira-toolkit
git pull
```

Then in Claude Code:

```
/reload-plugins
```

## Uninstalling

### Codex

```bash
codex plugin marketplace remove fhir-jira-toolkit
```

### Claude Code

```
/plugin uninstall fhir-jira@fhir-jira-toolkit
/plugin marketplace remove fhir-jira-toolkit
```

Optionally remove the local clone and config:

```bash
rm -rf /path/to/fhir-jira-toolkit   # only if locally cloned for this install
rm -rf ~/.config/fhir-jira-toolkit
```

External work directories under `/tmp/fhir-jira-work/` remain until cleaned.

---

## Troubleshooting

**`codex plugin marketplace add` fails.** Check that the Codex CLI is current,
that the path or `owner/repo` exists, and that the repo contains
`.agents/plugins/marketplace.json`.

**`/plugin marketplace add` says "unknown command".** Claude Code is too old.
Update and restart your terminal.

**Marketplace registers, but install fails.** In Codex, run
`codex plugin marketplace list`; in Claude Code, run `/plugin marketplace list`.
Check the exact marketplace name — case sensitivity matters. The marketplace
name is what's in `marketplace.json`'s top-level `name` field.

**Plugin installs but Codex does not use it.** Start a new thread. If still
missing, reopen the plugin directory and verify `fhir-jira` is installed and
enabled.

**Plugin installs but Claude Code slash commands don't appear.** Run
`/reload-plugins`. If still missing, run `/plugin` and check whether
`fhir-jira` is enabled.

**Fetched ticket JSON is missing expected fields** (e.g., empty
`Specification` or no `Resolution Description`). HL7's JIRA HTML may
have shifted since the parser was written. Re-run with `--dump-html`
and inspect the raw HTML at `<cache-dir>/_html-dumps/FHIR-NNNN.html`
to see what selectors would work. Extraction logic lives in the
`_IssuePageExtractor` class and `_fallback_regex_extract()` function
in `fetch_ticket.py`.

**Filter resolution fails with HTTP 401/403.** The filter is private.
Pass ticket keys explicitly instead, or have an HL7 admin make the
filter publicly shareable.

**`resolve_repo.py: UNRESOLVED: no Specification field match...`** The
ticket's `Specification` value isn't in the `names` list of any spec
entry. Run the script with `--ticket <path>` and look at the error — it
includes the exact string the ticket had. Add it to the appropriate
spec entry's `names` array in your override file.

**`gh pr create` fails with auth errors.** Run `gh auth status`. Re-auth
if needed: `gh auth refresh -s repo,workflow,read:org`.

**Publisher runs but `output/qa.json` doesn't exist.** Publisher likely
crashed mid-run. Look at its stdout for a stack trace. The skill won't
proceed past this — it'll surface the missing file.

**`local_exists: false` on a repo you actually have cloned.** The path
the plugin computed isn't where your clone lives. Either move/symlink
the clone, or set `local_path` explicitly in your override file for
that spec entry.

---

## What's installed where

```
<marketplace checkout>/                           ← the marketplace + plugin
<marketplace checkout>/.agents/plugins/           ← Codex marketplace metadata
<marketplace checkout>/.claude-plugin/            ← Claude Code marketplace metadata
~/.claude/plugins/cache/                          ← Claude Code's internal plugin cache (don't touch)
~/.config/fhir-jira-toolkit/repo-map.json         ← your repo-map overrides (edit freely)
/tmp/fhir-jira-staging/                           ← single-ticket staging cache
/tmp/fhir-jira-batch-<pid>/                       ← batch coordination cache
/tmp/fhir-jira-work/<github-slug>/                ← per-repo QA/message/verification artifacts
```

You can delete the `/tmp/` caches anytime; they're regenerated on next
run. The per-repo work directory holds your `qa-baseline.json` plus per-ticket
cached JSON and generated commit/PR bodies — keep it for traceability, remove
it when you want a clean slate.
