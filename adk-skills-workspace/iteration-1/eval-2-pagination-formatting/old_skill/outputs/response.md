# Eval 2 — Old Skills: "List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

## Skill Analysis

The user wants **all hosts with remediatable vulnerabilities**, prioritized for patching. This is a multi-step, pagination-heavy query. The relevant skills are:

- **multi-step-workflows** [PREFERRED]: The query cannot be answered with a single tool. It requires combining Vulnerability and Inventory data.
- **pagination-handling** [PREFERRED]: The user says "all my hosts" — this may span many pages. The pagination skill has a special exception: *"When the user asks for remediatable CVEs on a specific system, fetch all pages automatically."* However, this request is across ALL systems, not a specific one. The default behavior applies: fetch the first page, report the total, and offer to continue.
- **response-formatting** [GUIDANCE]: CVE lists should use a table with CVE ID, Severity, Affected Systems, Remediation Available. Host lists should use Display Name, OS, Last Check-in.
- **tool-invocation-rules** [STRICT]: Each action is a separate tool call with JSON arguments.
- **guardrails-safety** [STRICT]: Present severity labels exactly as reported. Note known exploits. Don't fabricate data.
- **efficient-counting** [PREFERRED]: Not directly needed here since the user wants actual data, not just a count. But limit=1 could be used as a pre-check.

## Step-by-Step Plan

### Step 1: Get systems with remediatable CVEs from the Vulnerability service

**Tool:** `vulnerability__get_systems`
**Arguments:** `{"limit": 50, "offset": 0}`
**Reasoning:** The `vulnerability__get_systems` tool returns systems tracked for CVE analysis. This is the correct tool for vulnerability-scoped queries per the **multi-step-workflows** skill's disambiguation table. I use `limit=50` as a sensible first page for host listings (per pagination-handling skill guidance). There is no direct `remediation` filter on `get_systems`, so I need to get the systems first and then check per-system CVEs.

However, re-reading the multi-step-workflows skill more carefully, `vulnerability__get_systems` does not have a `remediation` filter — only `vulnerability__get_system_cves` has `remediation=Applicable`. This means I cannot directly filter for "hosts with remediatable CVEs" in one call. I need a different approach.

**Revised approach:** Use `vulnerability__get_systems` to get all tracked systems, then for each system call `vulnerability__get_system_cves` with `remediation=Applicable, limit=1` to check if it has any remediatable CVEs (using the efficient-counting pattern to just check the total).

### Step 1 (revised): Fetch the first page of vulnerability-tracked systems

**Tool:** `vulnerability__get_systems`
**Arguments:** `{"limit": 50, "offset": 0}`
**Reasoning:** Get the first batch of systems. The pagination-handling skill says to fetch the first page, check total, and offer to continue if more exist.

**After response, check pagination metadata:**
- Read `meta.total_items` to know total system count.
- Read `links.next` — if not null, more pages exist.
- Read `meta.offset` + `meta.limit` for next offset.

### Step 2: For each system from Step 1, check for remediatable CVEs

**Tool:** `vulnerability__get_system_cves` (called once per system)
**Arguments for each system:** `{"system_id": "<host_id>", "remediation": "Applicable", "limit": 1, "offset": 0}`
**Reasoning:** Using the efficient-counting pattern from the **efficient-counting** skill — call with `limit=1` and read `meta.total_items` to get the count of remediatable CVEs for this system. This avoids fetching all CVE data per host just to check if remediatable CVEs exist.

For each system, I record:
- Whether `meta.total_items > 0` (has remediatable CVEs)
- The total count of remediatable CVEs (for prioritization)

### Step 3: For systems with remediatable CVEs, get severity breakdown

For each system that has remediatable CVEs (from Step 2), I need severity data to help the user prioritize. I call:

**Tool:** `vulnerability__get_system_cves`
**Arguments:** `{"system_id": "<host_id>", "remediation": "Applicable", "severity": "Critical", "limit": 1}`

Then repeat for `severity: "Important"`, `severity: "Moderate"`, `severity: "Low"` — using `limit=1` each time and reading `meta.total_items` to get the count per severity. This gives the user a prioritization breakdown without fetching all CVE details.

**Reasoning:** This follows the efficient-counting skill for "how many critical remediable CVEs are on host X?" pattern. The user wants to prioritize patching, so severity breakdown is essential.

### Step 4: Enrich with Inventory data (optional but recommended)

**Tool:** `inventory__get_host_details`
**Arguments:** `{"host_id": "<host_id>"}` (for each system with remediatable CVEs)
**Reasoning:** Per the **response-formatting** skill, host lists should include Display Name, OS, and Last Check-in. The vulnerability service may not return all these fields, so enriching with inventory data gives a better formatted response. Per **guardrails-safety**, if `last_seen` is older than 24 hours, I should note this.

### Step 5: Present results

**Format (per response-formatting skill):**

Present a summary line first, then a table sorted by total remediatable CVEs descending (highest priority first):

```
Found X systems with remediatable vulnerabilities out of Y total systems tracked for CVE analysis.

| Display Name | OS | Critical | Important | Moderate | Low | Total Remediatable | Last Check-in |
|---|---|---|---|---|---|---|---|
| host-prod-01 | RHEL 8.9 | 5 | 12 | 8 | 3 | 28 | 2 hours ago |
| host-prod-02 | RHEL 9.2 | 3 | 7 | 15 | 1 | 26 | 1 hour ago |
| ... | ... | ... | ... | ... | ... | ... | ... |

Systems with Critical or Important remediatable CVEs should be patched first.
Known-exploit CVEs (if any) are flagged — these warrant immediate attention regardless of severity.
```

If more than 20 systems have remediatable CVEs, show the top 20 (sorted by Critical+Important count descending) per the response-formatting inline list cap, and add: "...and N more systems have remediatable vulnerabilities. Would you like me to continue, or apply filters (e.g., Critical only, specific OS) to narrow down?"

### Pagination Handling Across Steps

**For Step 1 (system listing):** If `meta.total_items` from `vulnerability__get_systems` exceeds 50, I follow the pagination-handling default behavior: present the results from the first page and tell the user the total:

> "I've checked the first 50 of 342 systems for remediatable vulnerabilities. X of these 50 have remediatable CVEs. Would you like me to continue checking the remaining systems, or focus on these results first?"

I do NOT automatically paginate through all systems because:
1. The pagination-handling skill's auto-fetch exception is for "remediatable CVEs on a **specific system**", not across all systems.
2. For hundreds of systems, each needing multiple tool calls (Steps 2-3), the total number of API calls could be very large.
3. The default behavior is: fetch first page, report total, offer to continue.

**For Steps 2-3 (per-system CVE checks):** Each call uses `limit=1`, so there's no pagination needed within these calls — I'm using the efficient-counting pattern to read totals from metadata.

## Summary of Tool Calls

For a first page of 50 systems:

| Step | Tool | Calls | Purpose |
|---|---|---|---|
| 1 | `vulnerability__get_systems` | 1 | Get first page of tracked systems |
| 2 | `vulnerability__get_system_cves` | 50 | Check each system for remediatable CVEs (limit=1, remediation=Applicable) |
| 3 | `vulnerability__get_system_cves` | Up to 4 x N | Severity breakdown per system with remediatable CVEs (N = systems with CVEs) |
| 4 | `inventory__get_host_details` | N | Enrich display name, OS, last check-in for systems with CVEs |

**Worst case for 50 systems:** 1 + 50 + (4 x 50) + 50 = 301 tool calls. This is a lot.

**Optimization:** Instead of Step 3's per-severity counting, I could do a single call per system with a higher limit (e.g., `limit=20, remediation=Applicable, sort=-cvss_score`) to get the top remediatable CVEs with their severities in one call, then count severities from the returned data. This reduces calls but may miss CVEs beyond the limit.

**Practical approach:** For the first page, I would:
1. Get systems (1 call)
2. For each system, get remediatable CVEs with `limit=20, remediation=Applicable, sort=-cvss_score` (50 calls) — this gives both the count (from `meta.total_items`) and the severity distribution (from the returned data) in one call per system
3. Enrich with inventory details for systems that have remediatable CVEs (N calls)

This reduces to 1 + 50 + N calls for the first page, which is much more practical.
