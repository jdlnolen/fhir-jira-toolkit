# Working with the FHIR Specification — Authoring Reference

Authoritative reference for reading and editing FHIR specification source
files. Derived from and kept in sync with the CLAUDE.md in the FHIR
development repositories.

Use this during step 8 (Make the edit) to locate the right source file and
apply the correct edit pattern. When this file conflicts with general
knowledge, **this file wins** — it reflects the actual conventions in use.

---

## Build systems

### FHIR Core (`HL7/fhir`) — Gradle

Java-based FHIR Publisher invoked through Gradle. Requires Java 11+ and
substantial memory (16+ GB RAM; JVM heap configured at 12.8 GB in
`gradle.properties`).

```bash
# Standard full build (~20 min)
./gradlew publish

# Common flags
./gradlew publish --args="-nogen"       # skip generation, validation only
./gradlew publish --args="-noarchive"   # skip archive generation
./gradlew publish --args="-web"         # produce HL7 publication form
./gradlew publish --args="-offline"     # use cached dependencies if available

# Alternative cross-platform entry points
./publish.sh        # Unix/Mac/Linux (wraps gradlew)
publish.bat         # Windows
./build.sh          # CI build script
```

Key configuration files: `build.gradle.kts`, `gradle.properties`, `build.xml`.

Do **not** run `_genonce.sh` against the FHIR Core repo. That script is
for the IG Publisher toolchain; FHIR Core uses Gradle.

### Implementation Guides and Extensions Pack — IG Publisher

All IGs and the Extensions Pack use the same three shell scripts:

```bash
./_updatePublisher.sh    # download/update publisher.jar (~100 MB); run when stale
./_genonce.sh            # build the IG once (~2–5 min, requires 4+ GB RAM)
./_gencontinuous.sh      # continuous mode: rebuilds on every file change
```

Windows equivalents use `.bat`. Always run `_updatePublisher.sh` before
`_genonce.sh` if the publisher tool might be out of date. The
`publisher.jar` is downloaded automatically and must not be committed.

Key configuration files: `sushi-config.yaml`, `ig.ini`, `package-list.json`.

Do **not** run `./gradlew publish` against an IG repo.

---

## Directory structures

### FHIR Core source layout

```
fhir/
├── source/
│   └── {resource-name}/
│       ├── structuredefinition-{Resource}.xml   ← resource definition
│       ├── bundle-{Resource}-search-params.xml  ← search parameters
│       ├── {resource-name}-notes.xml            ← narrative notes (XHTML)
│       ├── {resource-name}-introduction.md      ← introduction text
│       ├── {resource-name}-examples.md          ← examples page
│       └── {resource-name}-example-*.xml        ← example instances
├── source/request/
│   └── request-spreadsheet.xml                  ← shared code systems (request-intent etc.)
├── build.gradle.kts
├── gradle.properties                             ← JVM heap config (12.8 GB)
└── build.xml
```

### IG and Extensions Pack layout

```
ig-name/
├── sushi-config.yaml            ← primary IG configuration
├── ig.ini                       ← IG Publisher config
├── package-list.json            ← package metadata
├── input/
│   ├── fsh/                     ← FSH source files — EDIT THESE
│   ├── pagecontent/             ← Markdown narrative pages — EDIT THESE
│   └── ignoreWarnings.txt       ← validation suppressions
├── fsh-generated/               ← DO NOT EDIT: generated from FSH by SUSHI
│   └── resources/               ← generated FHIR JSON resources
├── input-cache/                 ← cached tools (do not commit)
└── output/                      ← generated IG website (do not commit)
    ├── qa.html                  ← human-readable QA report
    └── qa.json                  ← machine-readable QA report
```

**Critical:** never edit `fsh-generated/resources/` directly. Changes are
overwritten on the next SUSHI compile. Edit the FSH source in `input/fsh/`
instead.

### IG toolchain

```
input/fsh/*.fsh
      │
      ▼  SUSHI compiles
fsh-generated/resources/*.json
      │
      ▼  IG Publisher generates
output/  (HTML documentation, QA report, validation results)
```

Use `_gencontinuous.sh` during iterative development — it watches for file
changes and rebuilds automatically, making the edit-review cycle much faster.
After changes settle, run `_genonce.sh` for a clean final build.

---

## Locating and editing source files

### Core FHIR: Resource Structure Definitions

**File pattern**: `source/{resource-name}/structuredefinition-{Resource}.xml`

```
source/specimen/structuredefinition-Specimen.xml
source/observation/structuredefinition-Observation.xml
source/servicerequest/structuredefinition-ServiceRequest.xml
```

Element definitions live in the `<differential>` block. After changing any
element name or type, always check and update the search parameters bundle.

### Core FHIR: Search Parameters

**File pattern**: `source/{resource-name}/bundle-{Resource}-search-params.xml`

```
source/specimen/bundle-Specimen-search-params.xml
source/observation/bundle-Observation-search-params.xml
```

Structure of a search parameter entry:

```xml
<entry>
  <resource>
    <SearchParameter>
      <id value="Specimen-additive"/>
      <code value="additive"/>
      <type value="reference"/>
      <expression value="Specimen.processing.additive.reference"/>
      <description value="Additive associated with container"/>
    </SearchParameter>
  </resource>
</entry>
```

Search parameter type by element type:

| Element type | Search parameter type |
|---|---|
| `canonical` | `token` (NOT `reference`) |
| `Reference` | `reference` |
| `uri` | `uri` |
| `CodeableReference.reference` | `reference` |
| `CodeableReference.concept` | `token` |

For `CodeableReference` elements, always add **two** search parameters:

```xml
<!-- Reference search -->
<SearchParameter>
  <id value="[Resource]-body-structure"/>
  <type value="reference"/>
  <expression value="[Resource].bodyStructure.reference"/>
</SearchParameter>

<!-- Token search -->
<SearchParameter>
  <id value="[Resource]-body-structure-code"/>
  <type value="token"/>
  <expression value="[Resource].bodyStructure.concept"/>
</SearchParameter>
```

### Core FHIR: Notes files

**File pattern**: `source/{resource-name}/{resource-name}-notes.xml`

XHTML fragments included in the generated documentation. Use for workflow
guidance, usage patterns, and implementation notes.

```xml
<div xmlns="http://www.w3.org/1999/xhtml">
  <a name="notes"></a>
  <h2>Notes:</h2>
  <ul>
    <li>Usage guidance here...</li>
  </ul>
</div>
```

### Core FHIR: Code Systems (spreadsheet format)

Shared code systems are defined in spreadsheet XML files. The most commonly
modified is the request-intent code system:

**File**: `source/request/request-spreadsheet.xml` (worksheet: `request-intent`)

Adding a new intent code:

```xml
<!-- Parent code (no parent reference in column 4) -->
<Row ss:AutoFitHeight="0" ss:Height="90">
  <Cell><Data ss:Type="String">proposal</Data></Cell>
  <Cell><Data ss:Type="Number">1</Data></Cell>
  <Cell><Data ss:Type="String">Proposal</Data></Cell>
  <Cell><Data ss:Type="String">Definition text...</Data></Cell>
</Row>

<!-- Child code — column 4 contains #parent-id -->
<Row ss:AutoFitHeight="0" ss:Height="90">
  <Cell><Data ss:Type="String">solicit-offer</Data></Cell>
  <Cell><Data ss:Type="Number">10</Data></Cell>
  <Cell ss:Index="4"><Data ss:Type="String">#1</Data></Cell>
  <Cell><Data ss:Type="String">Solicit Offer</Data></Cell>
  <Cell><Data ss:Type="String">Definition text...</Data></Cell>
</Row>
```

After adding or modifying codes, also increment `ExpandedRowCount` in the
table header.

### IG and Extensions Pack: FSH source

Primary source lives in `input/fsh/`. FSH (FHIR Shorthand) is a
human-readable syntax that SUSHI compiles into FHIR JSON resources. See
the sushi-config.yaml for IG-level settings.

Narrative content: `input/pagecontent/*.md` — standard Markdown files that
become HTML pages in the generated IG.

Review generated resources in `fsh-generated/resources/` after build to
confirm FSH compiled as expected, but do not edit them directly.

---

## Critical cross-cutting rules

### Always update Search Parameters when changing Structure Definitions

This is the most common source of build errors. When you modify a structure
definition:

1. If you rename an element (e.g., `instantiatesCanonical` → `instantiates`),
   update BOTH the StructureDefinition AND the search parameter expression.
2. If you change an element's type, verify the search parameter type is still
   correct (canonical elements → `token`, not `reference`).
3. If you add a new `CodeableReference` element, add two search parameters —
   one for `.reference` (type `reference`) and one for `.concept` (type `token`).

### Request resources all share the request-intent code system

When a ticket modifies `source/request/request-spreadsheet.xml` in any way,
EVERY Request resource's `intent` short description must be updated:

- ActivityDefinition
- CommunicationRequest
- DeviceRequest
- NutritionOrder
- RequestOrchestration
- ServiceRequest
- SupplyRequest

Find and update in each resource's StructureDefinition:

```xml
<short value="proposal | plan | directive | order | original-order | reflex-order | filler-order | instance-order | option"/>
```

### FHIR R6: bodySite → bodyStructure migration (OO resources)

An active migration across Orders and Observations resources. When working
on tickets for any affected resource, check whether a related migration
change is in scope for that ticket.

Affected resources:
- **Observation** — `bodySite` deprecated, `bodyStructure` changed to CodeableReference
- **DocumentReference** — `bodySite` renamed to `bodyStructure`
- **ObservationDefinition** — renamed and changed to CodeableReference
- **DeviceUsage** — `bodySite` renamed to `bodyStructure`
- **ServiceRequest** — `bodySite` deprecated, `bodyStructure` changed to CodeableReference

Standard pattern for `bodyStructure` elements:

```xml
<element id="[Resource].bodyStructure">
  <type>
    <code value="CodeableReference"/>
    <targetProfile value="http://hl7.org/fhir/StructureDefinition/BodyStructure"/>
  </type>
  <binding>
    <strength value="example"/>
    <description value="SNOMED CT Body Structures"/>
    <valueSet value="http://hl7.org/fhir/ValueSet/body-site"/>
  </binding>
</element>
```

Implementation checklist for a `bodyStructure` migration ticket:

1. Add `bodyStructure` with `CodeableReference(BodyStructure)` type
2. Add two search parameters: `[Resource]-body-structure` (`.reference`,
   type `reference`) and `[Resource]-body-structure-code` (`.concept`, type `token`)
3. Mark old `bodySite` as deprecated with clear migration guidance — do not delete it
4. Remove mutual-exclusion constraints between `bodySite` and `bodyStructure`
5. Use the `bodySite` extension URL (not `bodyStructure`) in any extension references

### `instantiates` patterns in Request resources

Several Request resources have or are migrating to a consolidated
`instantiates` pattern:

- `instantiatesCanonical`: references FHIR-defined protocols (ActivityDefinition, PlanDefinition)
- `instantiatesUri`: references external protocols

Some R6 tickets consolidate these to a single `instantiates` element of
type `canonical`. When working on such a ticket: update the StructureDefinition
AND the search parameters. The `canonical` type maps to search type `token`,
not `reference`.

### Record every change in the resource's "Changes since ballot" note (FHIR Core)

Applies to **FHIR Core (`HL7/fhir`) only.** IGs and the Extensions Pack have
their own change-log conventions; this pattern does not apply to them.

Whenever a ticket modifies a FHIR Core resource — its StructureDefinition,
search parameters, notes, examples, or narrative — you must also record that
change in the resource's **"Changes since 6.0.0-ballotN"** note so it appears on
the published resource page (e.g.
`https://build.fhir.org/deviceassociation.html#11.3`). Do this for **every
resource the ticket touches**, as part of the same edit — not as a follow-up.

**Location**: `source/<resource>/<resource>-introduction.xml`, near the top of
the file — after any `<blockquote class="ballot-note">` and immediately before
the `<a name="bnc"></a>` anchor / `<h2>Scope and Usage</h2>` heading.

**The note is a single `stu-note` blockquote with one `<li>` per ticket:**

```xml
<blockquote class="stu-note" style="background-color: lightblue">
	<p><b>Changes since 6.0.0-ballotN:</b></p>
	<ul>
		<li><a href="https://jira.hl7.org/browse/FHIR-NNNNN">FHIR-NNNNN</a> - short description of what changed</li>
	</ul>
</blockquote>
```

**Append vs. create:**

- If the resource's introduction already has a `Changes since 6.0.0-ballotN`
  blockquote for the current ballot, **add a new `<li>`** to its existing `<ul>`.
  Do not create a second blockquote.
- If it has none, **create** the blockquote in the location described above.

**Determining N (the ballot number):** N is the most recently *published*
ballot, which is **not** necessarily the `version` in `publish.ini` (the
in-development version is often one ahead). Match what the rest of the repo
already uses:

```bash
grep -rho 'Changes since 6\.0\.0-ballot[0-9]*' source | sort -u
```

Use the value other resources use. If the grep returns nothing, or more than one
value, **ask the user** which ballot number applies — do not guess.

**Description text:** one concise phrase describing the substantive change, in
spec-author voice — mirror the ticket's disposition rather than copying its
title verbatim. Example: `Binding relationship-status, relationship, and
status-reason valuesets to THO equivalent code systems`.

**Do not touch the neighbouring `ballot-note` blockquote.** The categorised
`<blockquote class="ballot-note">` (Non-compatible / Compatible substantive /
Non-substantive lists) is maintained separately by WG editors. Only add your
`stu-note` entry; leave the `ballot-note` structure alone.

---

## Resource-specific notes

### Specimen

**Structure Definition**: `source/specimen/structuredefinition-Specimen.xml`
**Search Parameters**: `source/specimen/bundle-Specimen-search-params.xml`
**Examples**: `source/specimen/specimen-example-*.xml`

`Specimen.processing.additive`:
- Type: `CodeableReference` (references Substance or uses inline codes)
- Target: `http://hl7.org/fhir/StructureDefinition/Substance`

HL7 v2-0371 codes for formalin preservatives (CodeSystem URL:
`http://terminology.hl7.org/CodeSystem/v2-0371`):

```xml
<additive>
  <concept>
    <coding>
      <system value="http://terminology.hl7.org/CodeSystem/v2-0371"/>
      <code value="F10"/>        <!-- 10% Formalin — NOT "FORM10" -->
      <display value="10% Formalin"/>
    </coding>
  </concept>
</additive>
```

Common codes: `F10` (10% Formalin), `BF10` (Buffered 10% formalin),
`CARS` (Carson's Modified 10% formalin).

---

## Build validation

### Finding QA output

| Build | Output dir | Error/warning counts | Feed to `parse_qa.py` with |
|---|---|---|---|
| IG Publisher (IGs, Extensions Pack) | `output/` | `output/qa.json` (+ `output/qa.html`) | `--current output/qa.json` |
| FHIR Core Gradle | `publish/` | **no qa.json** — the build log's `Summary: Errors=N, Warnings=N, Information messages=N` line | `--build-log <log>` |

**FHIR Core produces no `qa.json`.** The Gradle publish build writes the
generated site to `publish/` (not `output/`), and its validation summary is a
single line near the end of the build log:

```
Summary: Errors=0, Warnings=3752, Information messages=374
```

Capture the build log (e.g. `./gradlew publish | tee .jira-cache/build.log`)
and read the counts with `parse_qa.py --build-log .jira-cache/build.log`. For a
regression check, capture a baseline log on the unmodified default branch and
pass `--baseline-log`. The `qa_path` field from `resolve_repo.py` is empty for
FHIR Core for this reason — do not look for `output/qa.json`.

For IGs and the Extensions Pack, review `output/qa.html` for new validation
errors before committing; `parse_qa.py --current output/qa.json` reads the
machine-readable form.

### Validation after FSH edits (IGs)

After `_genonce.sh`, review the generated FHIR resources in
`fsh-generated/resources/` to confirm FSH compiled as expected. Common
FSH errors surface in terminal output; validation errors appear in
`output/qa.html`.

---

## Published URL to local output path mapping

When verifying that a change appears in the publisher's HTML output, map the
ticket's `Related URL` to a local file path under the publisher's output
directory.

### URL to output path

| Published URL pattern | Local output path | Notes |
|---|---|---|
| `https://hl7.org/fhir/<page>.html` | `publish/<page>.html` | FHIR Core Gradle — writes the generated site to `publish/` |
| `https://build.fhir.org/<page>.html` | `publish/<page>.html` | FHIR Core CI mirror |
| `https://hl7.org/fhir/extensions/<page>.html` | `output/<page>.html` | Extensions Pack (IG Publisher) |
| `https://build.fhir.org/ig/HL7/fhir-extensions/<page>.html` | `output/<page>.html` | Extensions Pack CI mirror |
| `https://hl7.org/fhir/us/core/<page>.html` | `output/<page>.html` | US Core IG (IG Publisher) |
| `https://build.fhir.org/ig/HL7/<repo>/<page>.html` | `output/<page>.html` | Any IG (IG Publisher) |

For FHIR Core, the Gradle build writes to `publish/<page>.html` (e.g.
`publish/servicerequest.html`). If it isn't there, discover it with
`find . -name '<page>.html' -path '*/publish/*' -newer .git/HEAD 2>/dev/null`.
For IGs and the Extensions Pack, `output/<page>.html` is reliable.

### Source file to output page (fallback when no Related URL)

When the ticket has no `Related URL`, derive the output page from the edited
source files:

| Source file pattern | Output page |
|---|---|
| `source/<resource>/structuredefinition-<Resource>.xml` | `<resource>.html` (discovered via find for FHIR Core) |
| `source/<resource>/<resource>-notes.xml` | `<resource>.html` |
| `source/<resource>/<resource>-introduction.md` | `<resource>.html` |
| `input/pagecontent/<page>.md` | `output/<page>.html` (IGs) |
| `input/fsh/<name>.fsh` | `output/StructureDefinition-<name>.html` (IGs, Extensions Pack) |

For FSH sources, the output filename depends on the resource type defined
in the FSH file. `StructureDefinition-<name>.html` is the most common
pattern, but `CodeSystem-<name>.html` or `ValueSet-<name>.html` may apply
for non-profile resources.

---

## Memory and performance

| Task | Min RAM | JVM heap | Typical time |
|---|---|---|---|
| FHIR Core full build | 16 GB | 12.8 GB | ~20 minutes |
| FHIR Core, generation only (`-nogen`) | 8 GB | 12.8 GB | ~5 minutes |
| IG build (`_genonce.sh`) | 4 GB | — (IG Publisher default) | 2–5 minutes |
| IG continuous build (`_gencontinuous.sh`) | 4 GB | — | seconds per change |

If a FHIR Core Gradle build fails with out-of-memory errors, close other
applications. The heap configuration in `gradle.properties` is the minimum
that works reliably. Do not lower it to speed up the build; it will fail.

---

## Governance

**All FHIR Core changes** (`HL7/fhir`) should go through the JIRA workflow.
Do not open PRs directly against `HL7/fhir` without a corresponding resolved
JIRA ticket — this is the HL7 governance model for the core specification.

**IG changes** may vary. US Core and other HL7-governed IGs typically also
use JIRA. For any IG, check the contributing guide before opening a direct PR.

CI/CD pipelines for the core spec publish automatically to build.fhir.org
after a PR merges — no manual publication step is needed.
