# IG Publisher `qa.json` — what to expect

The IG Publisher writes `output/qa.json` after every run. The schema has
shifted a few times; `parse_qa.py` handles all the variants we've seen.

## Fields the parser looks at, in order

1. **Newer top-level shorthand**
   - `errs` (number) — error count
   - `warnings` (number)
   - `hints` (number) — informational
   - `links` or `brokenlinks` (number)

2. **Older top-level**
   - `errors`, `warnings`, `info`, `brokenlinks`

3. **`summary` subobject** with the same keys as above

4. **Per-file fallback** — walks `qa.json["files"][*].messages[*].level`
   and counts by severity

## Severity normalization

| Source string             | Bucket    |
|---------------------------|-----------|
| `error`, `fatal`          | errors    |
| `warning`                 | warnings  |
| `information`, `info`, `hint` | info  |

## Practical tips

- Snapshot a baseline `qa.json` from the **unmodified default branch** before
  starting a session of work. Save it at `.jira-cache/qa-baseline.json`.
- The publisher does not always write `qa.json` if it crashes early. Check
  the publisher's exit code first, then the file.
- Some IGs write `qa.html` but not a full `qa.json`. If `qa.json` is missing
  but `qa.compare.txt` or `qa.txt` exist, fall back to grepping those —
  but treat the result as advisory and surface the limitation to the user.
- Errors increasing is a hard stop. Warnings increasing is a judgment call;
  the publisher generates new warnings when, e.g., a new code is introduced
  that doesn't yet have a definition in the value set.

## FHIR Core (Gradle build) vs IGs (IG Publisher)

The Extensions Pack and all IGs use the HL7 IG Publisher, which writes
`output/qa.json` in the format documented above.

**FHIR Core (`HL7/fhir`)** uses a Gradle build invoked via
`./gradlew publish`, which is a different toolchain. The output location
and `qa.json` format may differ. The parser's fallback path (counting
errors/warnings from per-file `messages` arrays) is the safer bet for
Gradle output; if that doesn't work for your run, dump the actual file
and check which schema it matches, then update `parse_qa.py`'s `counts()`
function if needed.

If the FHIR Core build writes its QA file somewhere other than
`output/qa.json`, pass the actual path explicitly:

```bash
parse_qa.py --current build/publish/qa.json --baseline .jira-cache/qa-baseline.json
```
