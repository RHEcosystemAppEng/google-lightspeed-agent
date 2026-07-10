# Eval 7: A2UI Rendering — With Skills

## User Query

> "Show me my top 10 critical CVEs sorted by CVSS score."

---

## Step-by-Step Plan

### Step 1: Call `vulnerability__get_cves` with targeted filters

This is a global CVE query (no specific system named), so per the **multi-step-workflows** skill's CVE disambiguation rule, I use `vulnerability__get_cves` (not `vulnerability__get_system_cves`).

Per the **tool-invocation-rules** skill, I apply the "Top/critical CVEs" recommended defaults and adjust the limit to match the user's request for 10 results:

```
tool: vulnerability__get_cves
args: {
  "impact": "7",
  "sort": "-cvss_score",
  "advisory_available": "true",
  "limit": 10
}
```

**Rationale for each argument:**

| Argument | Value | Reason |
|---|---|---|
| `impact` | `"7"` | String value `"7"` maps to Critical severity per tool-invocation-rules. The user asked for "critical CVEs." |
| `sort` | `"-cvss_score"` | Descending CVSS score sort — the skill states "always include for 'top' or severity queries." |
| `advisory_available` | `"true"` | String-typed boolean (not JSON `true`) — restricts to actionable CVEs with available advisories, per the recommended defaults. |
| `limit` | `10` | Integer matching the user's explicit "top 10" request. Per the pagination-handling skill, when the user specifies a quantity, use it directly — no follow-up offer needed. |

### Step 2: Process the response

After receiving the response, I extract from each CVE entry in the `data` array:
- **CVE ID** (e.g., `CVE-2024-XXXXX`)
- **Synopsis** (brief description of the vulnerability)
- **Severity** label (Critical)
- **CVSS Score** (numeric value)
- **Affected Systems** count
- **Known Exploit** status (`known_exploit` field)
- **Remediation Available** (Yes/No based on advisory availability)

Per the **guardrails-safety** skill, I present severity labels exactly as reported by the API without remapping. I also check for `known_exploit=true` entries — the skill states these "deserve extra emphasis regardless of severity label."

Per the **pagination-handling** skill, since the user explicitly asked for 10 and I requested `limit=10`, no pagination follow-up is needed. However, I note the `meta.total_items` value to inform the user of the total count (e.g., "Showing 10 of 342 critical CVEs").

### Step 3: Present results using the A2UI tool

Per the **response-formatting** skill's "A2UI Rich Rendering" section:

> When the `send_a2ui_json_to_client` tool is available, prefer rendering structured data as A2UI components instead of markdown tables. Use A2UI for: CVE and vulnerability lists [...]

Since the `send_a2ui_json_to_client` tool is available and this is a CVE list (structured data), I render the results as A2UI components rather than a markdown table.

```
tool: send_a2ui_json_to_client
args: {
  "json_payload": {
    "version": "0.9",
    "type": "column",
    "children": [
      {
        "type": "text",
        "content": "Top 10 Critical CVEs by CVSS Score",
        "style": "headline"
      },
      {
        "type": "text",
        "content": "Showing 10 of {meta.total_items} critical CVEs with available advisories, sorted by CVSS score."
      },
      {
        "type": "list",
        "children": [
          {
            "type": "card",
            "title": "CVE-2024-XXXXX",
            "children": [
              {
                "type": "row",
                "children": [
                  {"type": "text", "content": "Critical | CVSS: 9.8"},
                  {"type": "text", "content": "Known Exploit: Yes"}
                ]
              },
              {"type": "text", "content": "Synopsis: Remote code execution vulnerability in..."},
              {
                "type": "row",
                "children": [
                  {"type": "text", "content": "Affected Systems: 12"},
                  {"type": "text", "content": "Remediation: Available"}
                ]
              },
              {
                "type": "button",
                "label": "View affected systems",
                "prompt": "Show me the systems affected by CVE-2024-XXXXX"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

Each CVE is rendered as a **Card** within a **List**, containing:
- **Title**: The CVE ID
- **Row**: Severity + CVSS score alongside known exploit status
- **Text**: Synopsis of the vulnerability
- **Row**: Affected system count + remediation availability
- **Button**: "View affected systems" — triggers a follow-up query for that specific CVE

CVEs with `known_exploit=true` would receive additional visual emphasis (e.g., a "Known Exploit" indicator in the card).

### Step 4: Add contextual text alongside the A2UI payload

Per the response-formatting skill: "When the response mixes structured data with explanatory text, render the data portion as A2UI and include the explanation as plain text in the same response."

I include a brief plain-text summary alongside the A2UI rendering:

> "Here are your top 10 critical CVEs sorted by CVSS score. All have available advisories for remediation. 3 of these have known exploits in the wild — I've highlighted those. Would you like me to show the affected systems for any of these, or fetch details on a specific CVE?"

---

## Decision: A2UI vs. Markdown

**A2UI is the correct choice here.** The response-formatting skill explicitly states:

> When the `send_a2ui_json_to_client` tool is available, prefer rendering structured data as A2UI components instead of markdown tables. Use A2UI for: CVE and vulnerability lists [...]

This query produces a structured CVE list — exactly the scenario where A2UI should be used. A2UI provides several advantages over markdown for this use case:

1. **Interactive buttons**: Each CVE card includes a "View affected systems" button that triggers a follow-up query, enabling the user to drill down without typing
2. **Structured layout**: Cards with rows provide clear visual hierarchy for multi-field CVE data (ID, severity, CVSS, synopsis, affected systems, remediation status)
3. **Consistent rendering**: A2UI components render consistently across different client UIs, unlike markdown table support which varies

Markdown would only be appropriate if the `send_a2ui_json_to_client` tool were unavailable, or for the short explanatory text that accompanies the structured data.

---

## Skills Applied

| Skill | How it was applied |
|---|---|
| **tool-invocation-rules** | Used correct parameter names (`impact="7"` not `severity="Critical"`), string-typed boolean for `advisory_available`, included `sort` for a "top" query, followed the recommended defaults template |
| **multi-step-workflows** | Selected `vulnerability__get_cves` (global scope) over `vulnerability__get_system_cves` since no specific system was named |
| **pagination-handling** | Used `limit=10` matching the user's explicit request; no pagination follow-up needed. Report total from `meta.total_items` |
| **efficient-counting** | Not directly needed — the user asked for data, not a count. But `meta.total_items` from the response provides the total for context |
| **error-handling** | Ready to retry with reduced limit or narrower filters if `tool_result_too_large` occurs; would distinguish empty results from API failures |
| **guardrails-safety** | Present severity labels as-is; emphasize CVEs with known exploits; note the total count transparently |
| **response-formatting** | Render as A2UI components (Card + List) instead of markdown table since `send_a2ui_json_to_client` is available; add contextual plain text alongside |
