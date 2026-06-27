# Repo map — adding IGs and overriding defaults

The plugin ships with a default `repo-map.json` covering FHIR core, the
Extensions Pack, and a starter set of IGs. You'll likely need to add your
own IGs and adjust local clone paths. This doc explains how.

## File locations

Three locations, merged in this order (later wins for any given GitHub slug):

1. **Shipped defaults**: `${FHIR_JIRA_PLUGIN_ROOT}`, `${CODEX_PLUGIN_ROOT}`, or `${CLAUDE_PLUGIN_ROOT}` `/skills/fhir-jira-workflow/repo-map.json`
   — don't edit this; updates from the plugin will overwrite it.
2. **User-global override**: `~/.config/fhir-jira-toolkit/repo-map.json`
   — your personal settings, applies across all projects.
3. **Project-local override**: `./repo-map.local.json` — when CWD has one,
   it takes precedence. Useful for one-off setups.

To inspect the merged result:

```bash
PLUGIN_ROOT="${FHIR_JIRA_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}"
python3 "$PLUGIN_ROOT/skills/fhir-jira-workflow/scripts/resolve_repo.py" --list
```

## Schema

```jsonc
{
  "version": 1,
  "default_clone_root": "~/dev/hl7",
  "specifications": [
    {
      "names": ["Display name in JIRA Specification field", "alternate name"],
      "github": "HL7/fhir-something",
      "local_path": "~/dev/hl7/fhir-something",   // optional; computed from default_clone_root if absent
      "default_branch": "master",                  // advisory; SKILL verifies
      "publisher": "./_updatePublisher.sh && ./_genonce.sh",
      "qa_path": "output/qa.json",                 // optional; default output/qa.json
      "build_dirs": ["output", "temp", "input-cache"],  // optional; dirs to never edit/commit
      "url_patterns": [
        "hl7\\.org/fhir/us/something/",
        "build\\.fhir\\.org/ig/HL7/fhir-something"
      ]
    }
  ]
}
```

### Field details

- **`names`** — strings that can appear in the JIRA `Specification` custom
  field. Matching is case-insensitive substring on both directions, so
  `["US Core"]` matches `Specification = "US Core (US Core)"` and vice versa.
- **`github`** — the `org/repo` slug. This is the merge key — overrides
  match by this slug.
- **`local_path`** — optional. If absent, computed as
  `<default_clone_root>/<repo-name-without-org>`.
- **`default_branch`** — `master` for FHIR core and most older HL7 repos;
  `main` for newer IGs. The skill verifies via `git remote show origin`
  before using it, so a wrong value here is recoverable but noisy.
- **`publisher`** — exact shell command to run from the repo root. Two
  flavors in this codebase:
  - FHIR Core uses Gradle: `./gradlew publish`
  - The Extensions Pack and all IGs use the HL7 IG Publisher:
    `./_updatePublisher.sh && ./_genonce.sh`

  These are not interchangeable. Setting the wrong one will either fail
  immediately (missing script) or produce wrong outputs. The skill's
  verify-defaults step also `ls`'s for `_genonce.sh` and `gradlew` to
  cross-check whether the configured publisher matches reality.
- **`qa_path`** — relative path to the publisher's QA report. Optional;
  defaults to `output/qa.json` (the IG Publisher convention). FHIR Core's
  Gradle build may write the file somewhere else (e.g.,
  `build/publish/qa.json`); set this explicitly once you've confirmed
  where Gradle puts it.
- **`build_dirs`** — list of directory names (relative to repo root)
  that the publisher writes into. The skill uses this to (a) warn if you
  try to stage anything from one of them, and (b) suggest entries for
  `.git/info/exclude`. Optional; defaults to `["output", "temp"]`. The
  IG Publisher also creates `input-cache/`. FHIR Core's Gradle build
  uses `build/` and `.gradle/`.
- **`url_patterns`** — regex strings (Python `re` syntax). Used as fallback
  when the `Specification` field is missing or ambiguous. Match against
  any URL appearing in the ticket's `Related URL` field or description.

## Adding an IG

Create or edit `~/.config/fhir-jira-toolkit/repo-map.json`:

```json
{
  "version": 1,
  "specifications": [
    {
      "names": ["My IG", "MyIG"],
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

You don't need to repeat fields you're not overriding. To verify the
mapping picks up correctly, fetch a ticket from that IG and run:

```bash
python3 "$PLUGIN_ROOT/skills/fhir-jira-workflow/scripts/resolve_repo.py" \
  --ticket "$FHIR_JIRA_WORK_DIR/FHIR-NNNN.json"
```

## Changing your clone root

If you keep your HL7 clones somewhere other than `~/dev/hl7`, set the
`default_clone_root` in your user-global override and leave `local_path`
unset on the per-spec entries. They'll inherit the new root automatically.

```json
{
  "version": 1,
  "default_clone_root": "/work/hl7"
}
```

## Per-spec local_path overrides

Sometimes you want one specific repo elsewhere — e.g., a personal fork
checked out under a different name. Set `local_path` explicitly:

```json
{
  "specifications": [
    {
      "github": "HL7/fhir",
      "local_path": "/work/forks/fhir-jd"
    }
  ]
}
```

Note that `github` should still be the upstream slug — that's where PRs
go. If you want to PR against your fork instead, that's a different change
(adjust the `gh pr create --draft --repo ...` argument in the skill or override
locally).

## Resolution semantics in batch mode

In batch mode, `resolve_repo.py --group <comma-separated-paths>` produces:

```json
{
  "groups": {"HL7/fhir": ["FHIR-1"], "HL7/US-Core": ["FHIR-2"]},
  "unresolved": [{"key": "FHIR-3", "reason": "..."}]
}
```

The `unresolved` list is the actionable signal: those tickets either need
a new entry in the repo map, or their `Specification` / `Related URL` is
ambiguous and needs human review.
