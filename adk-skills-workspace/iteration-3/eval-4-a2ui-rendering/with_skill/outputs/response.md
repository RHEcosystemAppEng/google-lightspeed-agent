# Eval 4: A2UI Rendering — With Skill Response

## User Prompt

> "Show me my top 10 critical CVEs sorted by CVSS score."

---

## Step-by-Step Plan

### Step 1: Fetch the top 10 critical CVEs sorted by CVSS score

I would make a single tool call to the Vulnerability service using the confirmed filter parameters from the **tool-invocation-rules** skill:

```
tool: vulnerability__get_cves
args: {
  "limit": 10,
  "severity": "Critical",
  "sort": "-cvss_score",
  "affecting": true
}
```

**Rationale:**
- `limit: 10` — the user explicitly asked for "top 10", so I set the limit directly (per the **pagination-handling** skill: "Show me the top 3 CVEs on host X" -> use limit=3, no follow-up needed).
- `severity: "Critical"` — filters to Critical CVEs only, as the user requested. This is a confirmed parameter on `vulnerability__get_cves` per the **tool-invocation-rules** skill.
- `sort: "-cvss_score"` — sorts by CVSS score in descending order (the `-` prefix means descending), so the highest-scoring CVEs appear first. This is a confirmed sort parameter per the **tool-invocation-rules** skill.
- `affecting: true` — restricts to CVEs that actually affect at least one system in the user's infrastructure, making the results actionable rather than theoretical. This is a confirmed parameter per the **tool-invocation-rules** skill.

### Step 2: Check for known exploits (contextual enrichment)

Per the **guardrails-safety** skill, "CVEs with `known_exploit=true` deserve extra emphasis regardless of severity label." After receiving the results from Step 1, I would inspect the returned data for the `known_exploit` field on each CVE. If any of the top 10 have known exploits, I would flag them prominently in the output. This does not require a separate tool call — the data is included in the `vulnerability__get_cves` response.

### Step 3: Check pagination metadata

Per the **pagination-handling** skill, after receiving the response I check `meta.total_items` to see if there are more critical CVEs beyond the 10 returned. Since the user explicitly asked for "top 10," no automatic pagination follow-up is needed. However, I would include the total count in my response for context (e.g., "Showing top 10 of 87 critical CVEs").

### Step 4: Present the results using A2UI

Per the **response-formatting** skill's "A2UI Rich Rendering" section:

> "When the `send_a2ui_json_to_client` tool is available, prefer rendering structured data as A2UI components instead of markdown tables. Use A2UI for: CVE and vulnerability lists..."

I would use the `send_a2ui_json_to_client` tool to render the CVE list as rich A2UI components, following the CVE Vulnerability List pattern from Example 1 in the A2UI examples. The explanatory text (total count, known exploit warnings) would be included as plain text in the response alongside the A2UI rendering.

**Tool call:**

```
tool: send_a2ui_json_to_client
args: {
  "json_string": "<A2UI JSON payload — see below>"
}
```

**A2UI payload structure:**

```json
{
  "a2ui": [
    {
      "version": "v0.9",
      "createSurface": {
        "surfaceId": "main",
        "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
      }
    },
    {
      "version": "v0.9",
      "updateComponents": {
        "surfaceId": "main",
        "components": [
          {
            "component": "Column",
            "id": "cve_root",
            "children": ["cve_title", "cve_summary", "cve_list"]
          },
          {
            "component": "Text",
            "id": "cve_title",
            "text": "Top 10 Critical CVEs by CVSS Score",
            "usageHint": "h1"
          },
          {
            "component": "Text",
            "id": "cve_summary",
            "text": "Showing top 10 of 87 critical CVEs affecting your systems, sorted by CVSS score (highest first)."
          },
          {
            "component": "List",
            "id": "cve_list",
            "children": ["cve_card_1", "cve_card_2", "cve_card_3", "cve_card_4", "cve_card_5", "cve_card_6", "cve_card_7", "cve_card_8", "cve_card_9", "cve_card_10"]
          },
          {
            "component": "Card",
            "id": "cve_card_1",
            "children": ["cve_col_1"]
          },
          {
            "component": "Column",
            "id": "cve_col_1",
            "children": ["cve_1_id", "cve_1_details"]
          },
          {
            "component": "Text",
            "id": "cve_1_id",
            "text": "CVE-2024-21762",
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "cve_1_details",
            "children": ["cve_1_severity", "cve_1_cvss", "cve_1_systems", "cve_1_exploit"]
          },
          {
            "component": "Text",
            "id": "cve_1_severity",
            "text": "Severity: Critical"
          },
          {
            "component": "Text",
            "id": "cve_1_cvss",
            "text": "CVSS: 9.8"
          },
          {
            "component": "Text",
            "id": "cve_1_systems",
            "text": "Affected: 14 systems"
          },
          {
            "component": "Text",
            "id": "cve_1_exploit",
            "text": "Known Exploit: YES"
          }
        ]
      }
    }
  ]
}
```

The above shows the pattern for the first CVE card. Each of the 10 CVEs would follow the same Card -> Column -> [Text (CVE ID as h2), Row -> [Severity, CVSS, Affected Systems, Known Exploit]] structure. Key points:

- **Card** wraps each CVE entry for visual separation
- **Column** stacks the CVE ID heading and details row vertically
- **Text with `usageHint: "h2"`** renders the CVE ID as a heading
- **Row** arranges the metadata fields (severity, CVSS, affected systems, exploit status) horizontally
- A known-exploit field is added to each card per the **guardrails-safety** skill guidance

### Step 5: Accompany with plain text context

Per the **response-formatting** skill: "When the response mixes structured data with explanatory text, render the data portion as A2UI and include the explanation as plain text in the same response."

Alongside the A2UI payload, I would include plain text such as:

> Here are your top 10 critical CVEs sorted by CVSS score. 2 of these have known exploits in the wild and are flagged accordingly. These CVEs affect a total of 87 unique systems across your infrastructure. Would you like me to drill into any specific CVE for affected system details or remediation options?

This plain text provides actionable context and a natural follow-up prompt without cluttering the structured A2UI rendering.

---

## Summary of Tool Calls

| Order | Tool | Arguments | Purpose |
|---|---|---|---|
| 1 | `vulnerability__get_cves` | `limit: 10, severity: "Critical", sort: "-cvss_score", affecting: true` | Fetch the top 10 critical CVEs sorted by CVSS descending |
| 2 | `send_a2ui_json_to_client` | A2UI JSON payload with Column, List, Card, Row, Text components | Render the CVE list as rich UI components |

## Rendering Decision: A2UI (not markdown)

**I would use A2UI rendering**, not markdown tables. This is explicitly directed by the **response-formatting** skill:

> "When the `send_a2ui_json_to_client` tool is available, prefer rendering structured data as A2UI components instead of markdown tables. Use A2UI for: CVE and vulnerability lists."

The A2UI approach provides:
1. Structured Card-based layout for each CVE — visually scannable
2. Row-based metadata with severity, CVSS, affected systems, and exploit status
3. Consistent rendering across clients that support A2UI v0.9
4. Separation of data presentation (A2UI) from conversational context (plain text)

Plain markdown would only be used if `send_a2ui_json_to_client` were unavailable, or for the conversational portion of the response (summary text, follow-up questions, error messages).
