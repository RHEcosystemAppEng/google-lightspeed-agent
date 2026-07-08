# Eval 2: "List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

## Analysis & Skill Application

This request is a **multi-step workflow** (per the `multi-step-workflows` skill) that requires chaining calls across the Vulnerability service. The user wants:
1. All hosts with vulnerabilities
2. Filtered to only those with available remediations
3. Sorted/prioritized by severity for patching

This also triggers several other skills:
- **pagination-handling**: The exception rule applies — "When the user asks for remediatable CVEs on a specific system, fetch all pages automatically. Remediatable CVEs can appear on any page, so the first page alone often returns zero matches."
- **tool-invocation-rules**: Use confirmed filter parameters (`remediation`, `severity`, `sort`, `limit`, `offset`).
- **efficient-counting**: Not a pure count query, but I will use metadata totals to track pagination progress.
- **response-formatting**: Present results as a table with CVE ID, Severity, Affected Systems, Remediation Available, sorted by severity descending. Use A2UI components if the `send_a2ui_json_to_client` tool is available.
- **guardrails-safety**: This is a read-only analysis request (in scope). If the user asks to apply patches, I will note that the agent operates in read-only mode.

---

## Step-by-Step Tool Call Plan

### Step 1: Get all systems tracked for vulnerability analysis

**Reasoning:** The user wants hosts with remediatable vulnerabilities. Per the `multi-step-workflows` skill, I use `vulnerability__get_systems` (not `inventory__list_hosts`) because we need systems in the vulnerability-tracking scope. I start with a reasonable page size to get the first batch and check the total.

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 0}
```

**After receiving the response:** Read `meta.total_items` to learn how many systems exist. If `meta.total_items` > 50, I paginate through the remaining pages:

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 50}
```

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 100}
```

...and so on, advancing `offset` by 50 each time, applying the **stop conditions** from the `pagination-handling` skill:
1. `links.next` is `null`, OR
2. Next `offset` >= `meta.total_items`, OR
3. `data` has fewer elements than `limit` (last partial page) or is empty.

I collect the system ID and display name from each page.

**Error handling (per `error-handling` skill):** If any page returns `tool_result_too_large`, I reduce the page size from 50 to 20 and retry. If a 500/502/503 occurs, I retry once before reporting partial results.

### Step 2: For each system, get remediatable CVEs sorted by severity

**Reasoning:** For each system ID collected in Step 1, I query its CVEs filtered to only those with available remediations. Per the `pagination-handling` skill's exception rule, I **fetch all pages automatically** for remediatable CVE queries because remediatable CVEs can appear on any page.

I sort by CVSS score descending so the most critical CVEs appear first, supporting the user's patching prioritization goal.

**For each system (e.g., system_id = "abc-123"):**

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 0, "remediation": "Applicable", "sort": "-cvss_score"}
```

**After receiving the response:** Check `meta.total_items`. If there are more remediatable CVEs beyond the first page, automatically fetch all remaining pages:

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 20, "remediation": "Applicable", "sort": "-cvss_score"}
```

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 40, "remediation": "Applicable", "sort": "-cvss_score"}
```

...continuing until a stop condition is met. I use `limit=20` (not 100) because per the `error-handling` skill, smaller pages are less likely to trigger `tool_result_too_large`.

**Systems with zero remediatable CVEs:** Per the `guardrails-safety` skill, an empty result is a valid finding, not an error. I simply exclude that system from the final report (the user only wants hosts *with* remediatable vulnerabilities).

**Error handling:** If `tool_result_too_large` occurs, I add severity filters to narrow results (e.g., `severity=Critical` first, then `severity=Important`, etc.) and merge the results.

### Step 3: Aggregate and present results

**Reasoning:** Per the `response-formatting` skill, I need to present a connected, actionable response — not disconnected data dumps. I aggregate all results and present them prioritized for patching.

**Presentation structure:**

1. **Summary paragraph:** Total number of systems with remediatable vulnerabilities, total remediatable CVEs found, breakdown by severity.

2. **Prioritized host table** (sorted by most critical remediatable CVEs first):

| Host | OS | Critical | Important | Moderate | Low | Total Remediatable CVEs |
|---|---|---|---|---|---|---|
| prod-web-01 | RHEL 8.9 | 3 | 7 | 12 | 2 | 24 |
| prod-db-02 | RHEL 9.3 | 2 | 5 | 8 | 1 | 16 |
| ... | ... | ... | ... | ... | ... | ... |

3. **Top critical CVEs across all systems** (the user's patching priority):

| CVE ID | Severity | CVSS | Affected Systems | Known Exploit |
|---|---|---|---|---|
| CVE-2024-XXXX | Critical | 9.8 | prod-web-01, prod-db-02 | Yes |
| CVE-2024-YYYY | Critical | 9.1 | prod-web-01 | No |
| ... | ... | ... | ... | ... |

4. **Patching recommendation:** Prioritize CVEs with `known_exploit=true` first (per the `guardrails-safety` skill — "A Moderate CVE with a known exploit may warrant faster action than an Important CVE without one"), then Critical severity, then Important, etc.

5. **Read-only note** (per `guardrails-safety` skill): "I can help you identify and prioritize which systems to patch, but applying patches is done through your normal change management process."

If the `send_a2ui_json_to_client` tool is available (per `response-formatting` skill, A2UI section), I render the host table and CVE table as A2UI components instead of markdown tables, keeping the summary and recommendation text as plain text.

---

## Pagination Handling Summary

| Step | Tool | Pagination Strategy | Rationale |
|---|---|---|---|
| 1 | `vulnerability__get_systems` | Fetch all pages (limit=50, advancing offset) | Need complete system list to check each one |
| 2 | `vulnerability__get_system_cves` | Fetch all pages automatically per system (limit=20, `remediation=Applicable`) | Pagination-handling skill exception: remediatable CVEs must be fully fetched because they can appear on any page |

**Stop conditions applied at every page** (from `pagination-handling` skill):
1. `links.next` is `null`
2. Next `offset` >= `meta.total_items`
3. `data` has fewer elements than `limit` or is empty

**Error recovery** (from `error-handling` skill):
- `tool_result_too_large` -> reduce page size from 50/20 to 20/10 and retry
- HTTP 500/502/503 -> retry once, then report partial results with transparency about what failed
- HTTP 401/403 -> tell user to check permissions, do not retry
- Empty results -> valid finding, report as "no remediatable CVEs found"

## Known Exploit Prioritization

Per the `guardrails-safety` skill, CVEs with `known_exploit=true` deserve extra emphasis regardless of severity label. In Step 2, after collecting all remediatable CVEs, I would highlight any with known exploits at the top of the patching priority list, even if they are only Moderate severity. This is called out explicitly in the final presentation.

## Partial Data Transparency

Per the `guardrails-safety` skill's "Partial Data Transparency" section, if any system's CVE query fails while others succeed, I clearly separate what succeeded from what failed in the final response. For example: "Retrieved remediatable CVEs for 47 of 50 systems. The following 3 systems returned errors: [list]. You may want to retry for those systems."
