# Eval 2 — Old Skill Response

## Task

"List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

---

## Step-by-Step Plan

This query requires a multi-step workflow (per the **multi-step-workflows** skill) combining Vulnerability and Inventory data. The user wants to identify hosts with remediatable CVEs and prioritize them for patching. Here is the exact sequence of tool calls I would make:

### Step 1: Get systems from the Vulnerability service with a first page

**Reasoning:** The user wants hosts with vulnerabilities, so I use `vulnerability__get_systems` (per the multi-step-workflows skill's tool disambiguation table — vulnerability-scoped queries use `vulnerability__get_systems`, not `inventory__list_hosts`). I start with a reasonable page size to see the total fleet size tracked for CVE analysis.

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 0}
```

**After this call:** I read `meta.total_items` from the response metadata (per the **pagination-handling** skill) to know the total number of systems. I also collect each system's `id` and `display_name` from the `data` array.

### Step 2: Paginate through remaining systems (if needed)

**Reasoning:** Per the **pagination-handling** skill, I check the stop conditions after each call. If `meta.total_items` > 50, I continue fetching pages by advancing `offset`. However, since this is a "list all" request involving remediatable CVEs, I need the full list to cross-reference each host. I paginate through all pages.

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 50}
```

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 100}
```

*...continue until one of the stop conditions is met:*
- `links.next` is `null`, OR
- next `offset` >= `meta.total_items`, OR
- `data` has fewer elements than `limit` (last partial page) or is empty

If `tool_result_too_large` is returned, per the **error-handling** skill, I reduce the page size (e.g., from 50 to 20) and retry.

### Step 3: For each system, query remediatable CVEs (using limit=1 for counting first)

**Reasoning:** Per the **efficient-counting** skill, I first check how many remediatable CVEs each system has before fetching full details. This avoids unnecessary large fetches for systems with zero remediatable CVEs. I use `vulnerability__get_system_cves` with the `remediation=Applicable` filter (per the **tool-invocation-rules** skill, this is a confirmed parameter).

For each system ID collected in Steps 1-2:

```
tool: vulnerability__get_system_cves
args: {"limit": 1, "offset": 0, "remediation": "Applicable", "sort": "-cvss_score"}
```

**After this call:** I read `meta.total_items` to get the count of remediatable CVEs for this system. If the count is 0, I skip this system — it has no remediatable vulnerabilities. If the count is > 0, I record the system and its remediatable CVE count.

### Step 4: Fetch full remediatable CVE details for affected systems

**Reasoning:** Per the **pagination-handling** skill's exception rule — "When the user asks for remediatable CVEs on a specific system, fetch all pages automatically. Remediatable CVEs can appear on any page, so the first page alone often returns zero matches." Since the user wants to prioritize patching, I need severity details for each system's remediatable CVEs. I sort by `-cvss_score` so the most critical appear first.

For each system that had remediatable CVEs (count > 0) from Step 3:

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 0, "remediation": "Applicable", "sort": "-cvss_score"}
```

If a system has more than 20 remediatable CVEs, I paginate:

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 20, "remediation": "Applicable", "sort": "-cvss_score"}
```

*...continue until stop conditions are met (per pagination-handling skill).*

If `tool_result_too_large` is returned, per the **error-handling** skill, I reduce the page size to 10 or add a severity filter (e.g., `severity=Critical`) and retry.

### Step 5: Synthesize and present prioritized results

**Reasoning:** Per the **response-formatting** skill, I present results in a structured, actionable format. Per the **guardrails-safety** skill, I note that this agent operates in read-only mode — I can identify what to patch but cannot apply patches directly.

**Output format:**

I would lead with a brief summary paragraph, then present a table sorted by priority (systems with the most Critical/Important remediatable CVEs first):

**Summary:** "You have X systems with remediatable vulnerabilities out of Y total systems tracked. Here are your systems prioritized for patching, sorted by the number and severity of remediatable CVEs."

**Per-system table (CVE lists):**

| CVE ID | Severity | CVSS Score | Remediation Available |
|--------|----------|------------|----------------------|
| CVE-2024-XXXX | Critical | 9.8 | Yes |
| CVE-2024-YYYY | Important | 7.5 | Yes |
| ... | ... | ... | ... |

Per the **response-formatting** skill's inline list rule, I cap at 20 items per system. If more exist: "...and 47 more remediatable CVEs. Ask me to continue or filter by severity (e.g., Critical only)."

Per the **guardrails-safety** skill's partial data transparency rule, I would state how many results were shown vs. total: "Showing 20 of 342 remediatable CVEs for this host."

Per the **guardrails-safety** skill's modification requests rule, I would note: "I can identify affected systems and remediatable CVEs, but applying patches is done through your normal change management process."

---

## Pagination Handling Summary

Pagination is handled at two levels in this workflow:

1. **System-level pagination (Steps 1-2):** Paginate through all systems using `vulnerability__get_systems` with `limit=50` and advancing `offset`. Stop when any stop condition from the pagination-handling skill is met.

2. **CVE-level pagination (Steps 3-4):** For each system, first use `limit=1` to efficiently count remediatable CVEs (efficient-counting skill). Then fetch all pages of remediatable CVEs for systems that have them, since per the pagination-handling skill's exception rule, remediatable CVEs must be fetched across all pages.

3. **Error recovery:** If any call returns `tool_result_too_large`, reduce page size first (e.g., 50 -> 20 -> 10), then add filters if still too large (per error-handling skill).

4. **Large fleet optimization:** If the fleet has hundreds of systems, I would present results incrementally — show the top 10-20 most affected systems first and offer to show more, rather than making the user wait for all systems to be processed.
