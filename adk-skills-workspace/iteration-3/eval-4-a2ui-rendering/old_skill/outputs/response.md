# Eval 4: A2UI Rendering — Baseline Skills Response

## User Query

> "Show me my top 10 critical CVEs sorted by CVSS score."

---

## Step-by-Step Plan

### Step 1: Fetch the top 10 critical CVEs sorted by CVSS score

I would make a single tool call to the Vulnerability service with the appropriate filters and sorting:

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
- `limit: 10` — the user explicitly asked for top 10, so no pagination follow-up is needed (per pagination-handling skill: "Show me the top 3 CVEs on host X -> use limit=3, no follow-up needed").
- `severity: "Critical"` — filters to Critical severity only.
- `sort: "-cvss_score"` — sorts by CVSS score descending (highest first), giving us the "top" CVEs.
- `affecting: true` — restricts to CVEs that actually affect at least one system in the user's environment, making the results actionable rather than theoretical.

These are all confirmed parameters from the tool-invocation-rules skill, so no schema lookup is needed.

### Step 2: Present the results

After receiving the tool response, I would format the results as a **markdown table** following the response-formatting skill's CVE list format:

> Here are your top 10 critical CVEs, sorted by CVSS score:
>
> | CVE ID | Severity | CVSS Score | Affected Systems | Known Exploit | Remediation Available |
> |--------|----------|------------|------------------|---------------|-----------------------|
> | CVE-2024-XXXX | Critical | 10.0 | 47 | Yes | Yes |
> | CVE-2024-YYYY | Critical | 9.8 | 23 | No | Yes |
> | ... | ... | ... | ... | ... | ... |
>
> All 10 CVEs are Critical severity and affect systems in your environment. 3 have known exploits in the wild — I'd recommend prioritizing those for remediation. Would you like me to show which specific systems are affected by any of these CVEs?

**Additional details I would include:**
- Flag any CVEs with `known_exploit: true` with extra emphasis (per guardrails-safety skill: "CVEs with known_exploit=true deserve extra emphasis regardless of severity label").
- Note the total count from `meta.total_items` if there are more than 10 critical CVEs (e.g., "Showing 10 of 142 critical CVEs").
- Offer follow-up actions: drilling into affected systems per CVE, checking remediation details, or filtering further.

### Step 3 (conditional): Follow-up if requested

If the user wants to drill into a specific CVE, I would chain additional calls:

```
tool: vulnerability__get_cve_systems
args: {"cve_id": "CVE-2024-XXXX", "limit": 20}
```

Then optionally cross-reference with inventory for system context:

```
tool: inventory__get_host_details
args: {"host_id": "<host_id_from_previous_result>"}
```

---

## Presentation Decision: Markdown vs A2UI

**I would use markdown formatting, not the A2UI tool.**

The current skill set (response-formatting, tool-invocation-rules, multi-step-workflows, pagination-handling, efficient-counting, error-handling, guardrails-safety) contains no instructions, guidance, or even mentions of:
- The `send_a2ui_json_to_client` tool
- A2UI components (Card, List, Column, Row, Text, Button)
- Rich UI rendering
- Any alternative to markdown for presenting results

The response-formatting skill explicitly prescribes markdown tables as the output format for CVE lists:

> **CVE lists**: Use a table with columns: CVE ID, Severity (Critical/Important/Moderate/Low), Affected Systems, Remediation Available (Yes/No). Sort by severity descending unless the user specifies otherwise.

Since the skills are the agent's behavioral instructions, and no skill mentions A2UI or the `send_a2ui_json_to_client` tool, the agent would default to the only presentation format it has been instructed to use: markdown tables and text.

**Key gap identified:** Without a dedicated A2UI skill that teaches the agent when and how to use the `send_a2ui_json_to_client` tool, the agent will never produce rich UI components — even though the tool is available in its toolset. The tool's mere availability is not enough; the agent needs behavioral instructions (a skill) that:
1. Describe when to prefer A2UI over markdown (e.g., structured data like CVE lists, host inventories)
2. Provide the A2UI JSON schema and component catalog
3. Show examples of well-formed A2UI payloads for common result types
4. Define the decision logic: A2UI for structured/interactive data, markdown for explanatory text

---

## Summary

| Aspect | Behavior |
|--------|----------|
| **Tool calls** | 1 call: `vulnerability__get_cves` with limit=10, severity=Critical, sort=-cvss_score, affecting=true |
| **Pagination** | Not needed — user asked for exactly 10 |
| **Presentation format** | Markdown table (per response-formatting skill) |
| **A2UI usage** | Not used — no skill provides A2UI instructions |
| **Follow-up offered** | Yes — drill into affected systems, remediation details |
| **Error handling** | Would retry with reduced limit if tool_result_too_large; would report API errors transparently |
