# Tool Invocation Plan: "Show me the top critical and important CVEs affecting my systems"

## Analysis of the User Request

The user is asking for **top CVEs** filtered by **Critical and Important** severity levels that are **affecting their systems**. This is a landscape-level vulnerability query -- no specific system is named, so I need the global CVE list scoped to the user's environment. The word "top" implies sorting by severity/CVSS score, and "affecting my systems" means these should be CVEs that are actually impacting registered systems (not theoretical CVEs from the NVD).

## Step-by-Step Tool Call Plan

### Step 1: Fetch top Critical and Important CVEs with advisories available

**Tool:** `vulnerability__get_cves`
**Arguments:**
```json
{
  "impact": "5,7",
  "sort": "-cvss_score",
  "advisory_available": "true",
  "limit": 20
}
```

**Reasoning:**

- **Tool selection:** The user did not name a specific system, so this is a landscape-level query. Per the multi-step-workflows skill (CVE query disambiguation), when no specific system is named, use `vulnerability__get_cves` -- not `vulnerability__get_system_cves`.
- **`impact: "5,7"`:** Per the tool-invocation-rules skill, the `impact` parameter uses comma-separated numeric IDs. `7` = Critical, `5` = Important. This single parameter covers both severity levels in one call (no need for two separate calls).
- **`sort: "-cvss_score"`:** The user asked for "top" CVEs. Sorting by descending CVSS score surfaces the most severe vulnerabilities first. The tool-invocation-rules skill states: "always include sort for 'top' or severity queries."
- **`advisory_available: "true"`:** Per the tool-invocation-rules skill, this restricts results to actionable CVEs that have available advisories (errata/patches). This is the recommended default for CVE queries. Note this is a **string** `"true"`, not a JSON boolean `true` -- the MCP schema requires string-typed booleans for this parameter.
- **`limit: 20`:** The pagination-handling skill recommends 20 as the default page size for CVE lists. This gives enough results to show a meaningful "top" list without overwhelming the response.

This argument set matches exactly the "recommended defaults for common queries" pattern from the tool-invocation-rules skill:
```json
vulnerability__get_cves: {"impact": "5,7", "sort": "-cvss_score", "advisory_available": "true", "limit": 20}
```

### Step 2: Check pagination metadata and inform the user

**No additional tool call -- inspect the response metadata from Step 1.**

**Reasoning:**

- Per the pagination-handling skill, after receiving the response I check `meta.total_items` to see how many total CVEs match the filters.
- If the total is significantly more than 20, I tell the user: "Showing 20 of N Critical and Important CVEs (sorted by CVSS score). Would you like me to fetch more, or apply additional filters (e.g., only CVEs with known exploits) to narrow the results?"
- Per the guardrails-safety skill (Partial Data Transparency), I must state the total and how many I retrieved when presenting paginated results.

### Step 3: For the top CVEs, get affected system counts (optional enrichment)

**Tool:** `vulnerability__get_cve_systems` (called once per top CVE of interest)
**Arguments (example for the highest-scoring CVE):**
```json
{
  "cve": "CVE-YYYY-NNNNN",
  "limit": 5,
  "sort": "display_name"
}
```

**Reasoning:**

- The initial `vulnerability__get_cves` response includes per-CVE metadata such as the CVE ID, synopsis, CVSS score, severity, and the number of affected systems. This is usually sufficient for a "top CVEs" overview.
- However, if the user wants to see **which specific systems** are affected by the top CVEs, I would call `vulnerability__get_cve_systems` for each CVE of interest. Per the tool-invocation-rules skill: "Each tool call performs exactly one action. To query CVEs for three different hosts, make three separate tool calls."
- I would only make these calls for the most critical entries (e.g., the top 3-5 CVEs) to avoid excessive API calls, and I would ask the user before drilling into all 20.
- The `cve` parameter must be the full CVE ID string in the format `"CVE-YYYY-NNNNN"` (uppercase), **not** `cve_id`.

### Step 4: Present the results in a formatted table

**No tool call -- format and present the data.**

**Reasoning:**

- Per the response-formatting skill, CVE lists should be presented as a table with columns: **CVE ID, Synopsis, Severity, CVSS Score, Affected Systems, Remediation Available**.
- Sort by severity descending (which aligns with our `-cvss_score` sort).
- If any CVEs have `known_exploit: true`, per the guardrails-safety skill I would add extra emphasis: "A Moderate CVE with a known exploit may warrant faster action than an Important CVE without one."
- Cap the inline list at 20 items. If more exist, add a summary line: "...and N more. Ask me to continue or apply filters to narrow down."

## Summary of Tool Calls

| Step | Tool | Key Arguments | Purpose |
|------|------|---------------|---------|
| 1 | `vulnerability__get_cves` | `impact="5,7"`, `sort="-cvss_score"`, `advisory_available="true"`, `limit=20` | Fetch top Critical+Important CVEs with available advisories, sorted by CVSS score |
| 2 | (inspect metadata) | -- | Check `meta.total_items` and report pagination status |
| 3 | `vulnerability__get_cve_systems` | `cve="CVE-YYYY-NNNNN"`, `limit=5` | (Optional) Get affected system names for the top CVEs if the user wants details |
| 4 | (format response) | -- | Present results as a severity-sorted table with remediation status |

## Key Skill-Driven Decisions

1. **Tool-invocation-rules:** Used the exact recommended defaults for "Top/critical CVEs" queries. Used string-typed `"true"` for `advisory_available` (not JSON boolean). Used comma-separated impact IDs `"5,7"` for multi-severity filtering in a single call.
2. **Multi-step-workflows:** Selected `vulnerability__get_cves` (global scope) over `vulnerability__get_system_cves` (per-system scope) because no specific system was named.
3. **Pagination-handling:** Set `limit=20` as the default for CVE lists. Will report total count from `meta.total_items` and offer to fetch more or apply filters.
4. **Efficient-counting:** Not directly applicable here since the user wants to see the actual CVE data, not just a count. However, if the user follows up with "how many critical CVEs do I have?", I would use `limit=1` and read `meta.total_items` instead of paginating.
5. **Error-handling:** If the initial call returns `tool_result_too_large`, I would retry with `limit=10` and `impact="7"` (Critical only) to narrow the result set before asking the user to apply filters.
6. **Guardrails-safety:** Present severity labels exactly as reported by the API. Emphasize CVEs with `known_exploit=true`. Note pagination transparency ("Showing 20 of N").
7. **Response-formatting:** Use a structured table with CVE ID, Synopsis, Severity, CVSS Score, Affected Systems, and Remediation Available columns. Sort by severity descending.
