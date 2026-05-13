# Install instructions

Claude Code's plugin system is **marketplace-based**. You add a marketplace
(which can be a local directory), then install plugins from that
marketplace. This bundle ships as a marketplace containing one plugin.

## Step 0 — Prerequisites

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

### Option A — From GitHub (recommended)

Open Claude Code. In any conversation, run:

```
/plugin marketplace add <owner>/fhir-jira-toolkit
```

Replace `<owner>` with the GitHub org or username hosting the repo
(e.g., `jdln/fhir-jira-toolkit`).

Expected output:

```
✓ Fetching marketplace registry...
✓ Adding fhir-jira-toolkit marketplace

Available plugins:
  • fhir-jira

Run /plugin install <name> to install
```

### Option B — From a local clone

If you prefer a local install, or GitHub is unreachable:

```bash
git clone https://github.com/<owner>/fhir-jira-toolkit.git ~/.claude/marketplaces/fhir-jira-toolkit
```

Then in Claude Code:

```
/plugin marketplace add ~/.claude/marketplaces/fhir-jira-toolkit
```

### Troubleshooting

- **`unknown command`** — your Claude Code is too old. Update with
  `npm install -g @anthropic-ai/claude-code` (or your install method)
  and restart your terminal.
- **`marketplace.json not found`** — the path or repo is wrong. Check
  that `.claude-plugin/marketplace.json` exists at the root.
- **`invalid marketplace.json`** — the file is malformed. Check for
  syntax errors.

To confirm:

```
/plugin marketplace list
```

You should see `fhir-jira-toolkit` listed.

---

## Step 3 — Install the plugin from the marketplace

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

## Step 4 — Verify the slash commands are available

In a chat, type `/` and look for autocomplete suggestions. You should see:

- `/fhir-jira`
- `/fhir-jira-batch`

If they don't appear:

1. Type the full name (`/fhir-jira` and press space) — sometimes
   autocomplete is lazy. The command name should turn blue once recognized.
2. Run `/reload-plugins` — picks up changes without restarting.
3. Restart Claude Code — plugin discovery happens at session start.

---

## Step 5 — Configure your clone root (one-time)

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

## Step 6 — Verify repo resolution points where you think

Ask Claude to verify in a chat:

```
Run resolve_repo.py --list and show me the results
```

Or run the script directly (if you have a local clone):

```bash
python3 ~/.claude/marketplaces/fhir-jira-toolkit/plugins/fhir-jira/skills/fhir-jira-workflow/scripts/resolve_repo.py --list
```

You should see the five shipped specs with their resolved local paths.
Sanity-check that each `local:` path matches where your clone actually
lives. Any path that's wrong is a path you'll need to fix (either by
moving the clone, symlinking, or adding a per-spec `local_path` override
in your config — see `plugins/fhir-jira/skills/fhir-jira-workflow/references/repo-map.md`).

For specs whose clones you don't have yet, that's fine — the plugin will
ask before doing anything in those repos.

---

## Step 7 — Capture per-repo QA baselines (one-time per repo)

The skill compares each publisher run against a `qa-baseline.json` for
that repo. Establish the baseline on a clean default branch **before**
any ticket work in that repo:

```bash
# FHIR Core
cd ~/dev/hl7/fhir
git checkout master && git pull
./gradlew publish
mkdir -p .jira-cache
cp output/qa.json .jira-cache/qa-baseline.json   # adjust path if Gradle writes elsewhere

# Extensions Pack or any IG
cd ~/dev/hl7/US-Core              # or whichever
git checkout master && git pull   # or main, per the repo
./_updatePublisher.sh && ./_genonce.sh
mkdir -p .jira-cache
cp output/qa.json .jira-cache/qa-baseline.json
```

If the FHIR Core Gradle build writes its QA report somewhere other than
`output/qa.json` (it may be `build/publish/qa.json` or similar), adjust
the `cp` source path accordingly. Run the build once and `find . -name qa.json`
to locate it on first setup.

Repeat in every repo you'll touch. Each repo gets its own baseline.

Add `.jira-cache/` to your global gitignore so it never leaks into commits:

```bash
git config --global core.excludesfile ~/.gitignore_global
echo '.jira-cache/' >> ~/.gitignore_global
```

If you skip this step, the QA delta block in your PR bodies will show
absolute counts only ("warnings: 142") instead of deltas. Not harmful,
just less informative.

---

## Step 8 — Smoke test against a real ticket

Pick a low-stakes, already-resolved FHIR ticket. In Claude Code:

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
5. **Commit and PR.** Verify the PR body has the "What changed" synopsis,
   the "Files touched" list, and the QA delta table. The commit message
   (not the PR body) carries the `Disposition:` and `Ticket:` trailers.

If anything goes wrong, the script outputs live in `<repo>/.jira-cache/`
— that's your debugging trail.

---

## Updating the plugin

If you installed from GitHub, Claude Code pulls the latest version
automatically when the marketplace is refreshed. To force a refresh:

```
/reload-plugins
```

If you installed from a local clone, pull the latest and reload:

```bash
cd ~/.claude/marketplaces/fhir-jira-toolkit
git pull
```

Then in Claude Code:

```
/reload-plugins
```

## Uninstalling

```
/plugin uninstall fhir-jira@fhir-jira-toolkit
/plugin marketplace remove fhir-jira-toolkit
```

Optionally remove the local clone and config:

```bash
rm -rf ~/.claude/marketplaces/fhir-jira-toolkit   # only if locally cloned
rm -rf ~/.config/fhir-jira-toolkit
```

Per-repo `.jira-cache/` directories remain — delete them per-repo if you
want a clean slate.

---

## Troubleshooting

**`/plugin marketplace add` says "unknown command".** Claude Code is too
old. Update and restart your terminal.

**Marketplace registers, but `/plugin install fhir-jira@fhir-jira-toolkit`
fails.** Run `/plugin marketplace list` and check the exact marketplace
name — case sensitivity matters. The marketplace name is what's in
`marketplace.json`'s top-level `name` field.

**Plugin installs but slash commands don't appear.** Run `/reload-plugins`.
If still missing, run `/plugin` and check whether `fhir-jira` is enabled.

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
~/.claude/marketplaces/fhir-jira-toolkit/        ← the marketplace + plugin (read-only after install)
~/.claude/plugins/cache/                          ← Claude Code's internal plugin cache (don't touch)
~/.config/fhir-jira-toolkit/repo-map.json         ← your repo-map overrides (edit freely)
<each-repo>/.jira-cache/                          ← per-repo scratch (gitignored)
/tmp/fhir-jira-staging/                           ← single-ticket staging cache
/tmp/fhir-jira-batch-<pid>/                       ← batch coordination cache
```

You can delete the `/tmp/` caches anytime; they're regenerated on next
run. The `.jira-cache/` per-repo holds your `qa-baseline.json` plus
per-ticket cached JSON and generated commit/PR bodies — keep it for
traceability, blow it away when you want a clean slate.
