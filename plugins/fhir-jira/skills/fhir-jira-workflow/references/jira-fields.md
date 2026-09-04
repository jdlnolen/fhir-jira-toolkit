# HL7 JIRA fields — what the scraper extracts

The `fetch_ticket.py` script fetches the public browse URL
`https://jira.hl7.org/browse/<KEY>` with `urllib` and extracts fields
from the rendered HTML using Python's stdlib `html.parser`. No
authentication is required for public FHIR tickets.

For filter resolution it uses JIRA's built-in XML export view at
`/sr/jira.issueviews:searchrequest-xml/<id>/SearchRequest-<id>.xml`,
which also works without auth for publicly-shared filters.

## Output schema

```json
{
  "key": "FHIR-12345",
  "url": "https://jira.hl7.org/browse/FHIR-12345",
  "summary": "Top-level ticket title",
  "status": "Closed",
  "resolution": "Persuasive with Modification",
  "issuetype": "Change Request",
  "description": "Reporter's narrative, plain text with links inlined",
  "fields": {
    "Specification": "FHIR Core (FHIR)",
    "Related URL": "https://hl7.org/fhir/observation.html",
    "Related Artifact(s)": "Observation",
    "Resolution Description": "Authoritative disposition narrative",
    "Change Impact": "Compatible, substantive",
    "Work Group": "Patient Care"
  },
  "fetched_at": "2026-05-12T16:00:00Z"
}
```

Custom-field labels are taken verbatim from the JIRA UI's rendered
labels (e.g., `Specification`, `Related URL`). They're stored as keys
in the `fields` object. Downstream scripts look up fields by these
display names.

## Extraction strategy

Two passes:

1. **`_IssuePageExtractor` (HTMLParser subclass)** — walks the DOM with
   proper depth tracking. Captures:
   - Core fields by element id (`summary-val`, `status-val`,
     `resolution-val`, `type-val`, `priority-val`)
   - Custom fields by pairing `<strong class="name">Label:</strong>`
     with the next value element (id ending in `-val` or class `value`)
   - Description block (id `description-val` or
     `div.user-content-block`) including embedded link hrefs
2. **`_fallback_regex_extract`** — fills in any core fields the parser
   missed using simple regex against the raw HTML.

Both passes are best-effort. JIRA Server's DOM is stable across
versions but plugin themes can shift things. The `--dump-html` flag
saves the raw page so you can inspect when extraction fails.

## Description links fallback

If a ticket has no `Related URL` custom field but the description body
contains URLs, the first few are stored in
`fields["_description_links"]` (prefixed with `_` to indicate it's a
synthetic hint, not a real JIRA field). `resolve_repo.py` uses this as
a URL-pattern fallback when repo resolution needs more signal.

## FHIR resolution categories

The `resolution` value tells you the disposition class:

- **Persuasive** — change request is accepted as-is
- **Persuasive with Modification** — accepted with adjustments (read carefully)
- **Not Persuasive** — rejected
- **Not Persuasive with Modification** — rejected, but related change may be made
- **Considered for Future Use** — deferred

You should only implement **Persuasive** and **Persuasive with Modification**
tickets. If the resolution is anything else, stop and confirm with the user.

## Ballot impact classification

For FHIR Core resource changes, `fields["Change Impact"]` determines where
the ticket is documented in the resource page's categorized Note to Balloters:

- `Non-compatible` -> **Non-compatible**
- `Compatible, substantive` or `Compatible substantive` ->
  **Compatible substantive**
- `Non-substantive` -> **Non-substantive**

Treat this custom field as the primary classification. When it is absent, an
obvious technical correction may be classified from the actual change and
ticket type, with the basis captured in the published-output QA verdict. Stop
and ask the user when the impact is ambiguous.

## Filter resolution

```
GET https://jira.hl7.org/sr/jira.issueviews:searchrequest-xml/<ID>/SearchRequest-<ID>.xml?tempMax=1000
```

Returns XML containing every issue matching the filter. The scraper
extracts `<key>FHIR-NNNN</key>` elements via regex. `tempMax=1000`
caps the result set; if you have more, raise this or paginate.

If the filter is private, the endpoint returns HTTP 401/403. Pass
ticket keys explicitly instead.

## Why not the REST API

HL7's JIRA REST API at `/rest/api/2/issue/<KEY>` requires
authentication. The browse URL at `/browse/<KEY>` does not. The
scraper uses the public URL on purpose — zero auth, zero deps beyond
the Python standard library.

If you ever need to read auth-protected tickets, the cleanest extension
is to add an HTTP-Basic-auth path using a JIRA API token, while keeping
the unauthenticated browse-URL path as the default.
