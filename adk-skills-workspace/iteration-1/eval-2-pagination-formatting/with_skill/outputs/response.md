# Eval 2: "List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

## Analysis of the Request

The user wants:
1. Hosts that have **remediatable** vulnerabilities (i.e., vulnerabilities with available remediations)
2. Results organized for **patching prioritization** (severity-based ordering)

This is a multi-step workflow (per `multi-step-workflows` skill) that requires combining Vulnerability and Inventory APIs. It also triggers the **pagination-handling** skill's exception rule: "When the user asks for remediatable CVEs on a specific system, fetch all pages automatically."

However, since the user is asking across **all** systems (not a specific one), the approach is to find systems with remediatable CVEs via the Vulnerability service, then enrich with Inventory details.

---

## Step-by-Step Plan

### Step 1: Get systems with remediatable vulnerabilities (first page)

**Tool:** `vulnerability__get_systems`
**Arguments:**
```json
{
  "limit": 50,
  "offset": 0,
  "sort": "-rules_severity"
}
```

**Reasoning:**
- Per `multi-step-workflows` skill: `vulnerability__get_systems` returns "only systems tracked for CVE analysis" — this is the correct tool since we need vulnerability-scoped system data, not a general inventory listing.
- Per `tool-invocation-rules` skill: use native JSON types, omit unneeded optional args.
- Per `pagination-handling` skill: "fetch the first page with a sensible default (e.g., 50 for host listings)."
- Sorting by `-rules_severity` puts the most critical systems first, aligning with the user's patching prioritization goal.

**After receiving the response:**
- Read `meta.total_items` (or equivalent metadata field) to know the full count.
- Read the system list from `data`.

---

### Step 2: Paginate through remaining systems (if more exist)

**Condition:** Only if `meta.total_items` > 50 (i.e., more pages exist).

Per the `pagination-handling` skill, the user asked for "all my hosts" with remediatable vulnerabilities. This is a listing request, not a counting question, so I present the first page and offer to continue.

However, per the **pagination exception rule**: "When the user asks for remediatable CVEs on a specific system, fetch all pages automatically. Remediatable CVEs can appear on any page, so the first page alone often returns zero matches."

Since this query is across all systems (not a specific one), I follow the **default behavior**: present the first page, report the total, and offer to fetch more or apply filters.

If the total is manageable (e.g., under 200), I would paginate through all pages automatically since the user said "all." For each subsequent page:

**Tool:** `vulnerability__get_systems`
**Arguments:**
```json
{
  "limit": 50,
  "offset": 50
}
```

Then `offset: 100`, `offset: 150`, etc.

**Stop conditions** (per `pagination-handling` skill):
1. `links.next` is `null`, OR
2. Next `offset` >= `meta.total_items`, OR
3. `data` has fewer elements than `limit` (last partial page) or is empty.

---

### Step 3: For each system, get its remediatable CVEs

For each system returned in Steps 1-2, I need to find which CVEs are remediatable. Per `tool-invocation-rules` skill: "each tool call performs exactly one action." So I call once per system.

**Tool:** `vulnerability__get_system_cves`
**Arguments (per system):**
```json
{
  "system_id": "<host-uuid-from-step-1>",
  "limit": 20,
  "offset": 0,
  "remediation": "Applicable",
  "sort": "-cvss_score"
}
```

**Reasoning:**
- Per `tool-invocation-rules` skill: `vulnerability__get_system_cves` supports `remediation` (Applicable) to filter to only CVEs with available remediations.
- Sorting by `-cvss_score` puts highest-severity CVEs first for patching prioritization.
- Per `tool-invocation-rules`: `status` and `remediation` are confirmed parameters — no need to call `vulnerability__get_openapi`.
- Per the `pagination-handling` exception rule: since this is a remediatable CVE query on a specific system, **fetch all pages automatically**. Remediatable CVEs can appear on any page.

**Pagination for each system's CVEs:**
If `meta.total_items` > 20, continue fetching with `offset: 20`, `offset: 40`, etc., applying the same stop conditions as Step 2.

---

### Step 4: Enrich with host details from Inventory (optional, for context)

If the vulnerability response does not include enough host context (OS version, last check-in), I enrich with Inventory data.

**Tool:** `inventory__get_host_details`
**Arguments:**
```json
{
  "host_id": "<host-uuid>"
}
```

**Reasoning:**
- Per `multi-step-workflows` skill: "cross-reference with `inventory__get_host_details` for system context."
- Per `response-formatting` skill: host listings should include "Display Name, OS (e.g., RHEL 8.9), Last Check-in."
- Per `guardrails-safety` skill: "note the `last_seen`/`updated` timestamp if it's older than 24 hours — the information may be outdated."

---

### Step 5: Synthesize and present the response

Per `response-formatting` skill, I format the output as follows:

**Summary paragraph** (per "Mixed results" rule): brief overview connecting the data.

**Host table** sorted by severity priority (most critical first):

| Display Name | OS | Last Check-in | Critical CVEs | Important CVEs | Total Remediatable | Top CVE |
|---|---|---|---|---|---|---|
| prod-web-01 | RHEL 8.9 | 2 hours ago | 3 | 7 | 15 | CVE-2024-XXXX |
| prod-db-02 | RHEL 9.2 | 1 hour ago | 1 | 4 | 8 | CVE-2024-YYYY |

**Per `response-formatting` skill:**
- Cap inline lists at 20 items. If more hosts exist: "...and 47 more. Ask me to continue or apply filters to narrow down."
- Per `guardrails-safety` skill ("Partial Data Transparency"): "Showing 20 of 342 hosts with remediatable CVEs."

**Patching priority guidance:**
- Per `guardrails-safety` skill: emphasize CVEs with `known_exploit=true` regardless of severity label.
- Per `guardrails-safety` skill: note production vs. non-production context if discernible.
- Per `guardrails-safety` skill (Modification requests): "I can show you which systems are affected and whether remediations are available, but applying patches is done through your normal change management process."

---

## Error Handling Throughout

Per `error-handling` skill:
- If any tool call returns `tool_result_too_large`: reduce `limit` (e.g., from 50 to 20), then add filters (e.g., `severity=Critical`), then scope to specific systems.
- If a tool returns 401/403: tell the user to check permissions; do not retry.
- If a tool returns 500/502/503: retry once, then report the service is temporarily unavailable.
- Empty results are findings, not failures: "No remediatable vulnerabilities were found on any of your systems" is valid and useful.

---

## Example Response to the User

> I found **87 systems** in your environment that are tracked for vulnerability analysis. Of those, **34 have remediatable vulnerabilities**. Here are the top 20 prioritized by severity:
>
> | Host | OS | Last Check-in | Critical | Important | Total Remediatable | Top CVE |
> |---|---|---|---|---|---|---|
> | prod-web-01 | RHEL 8.9 | 2h ago | 3 | 7 | 15 | CVE-2024-1234 |
> | prod-db-02 | RHEL 9.2 | 1h ago | 1 | 4 | 8 | CVE-2024-5678 |
> | ... | ... | ... | ... | ... | ... | ... |
>
> ...and 14 more hosts with remediatable CVEs.
>
> **Priority recommendations:**
> - **prod-web-01** has 3 Critical CVEs including CVE-2024-1234 which has a known exploit in the wild — this should be your top patching priority.
> - 2 hosts have not checked in for over 24 hours — their vulnerability data may be outdated.
>
> I can look up your CVE data in more detail, show the full CVE list for any specific host, or continue showing more hosts. Applying patches would be done through your normal change management process.

---

## Skills Applied

| Skill | How It Was Used |
|---|---|
| `tool-invocation-rules` [STRICT] | Correct tool names, JSON argument types, confirmed filter parameters (`remediation`, `severity`, `sort`), one action per call |
| `guardrails-safety` [STRICT] | Severity interpretation, known exploit emphasis, stale data warnings, partial data transparency, read-only scope statement |
| `multi-step-workflows` [PREFERRED] | Chained Vulnerability -> Inventory calls; used `vulnerability__get_systems` (not `inventory__list_hosts`) for vuln-scoped listing |
| `pagination-handling` [PREFERRED] | Default first-page fetch with offer to continue; exception rule for per-system remediatable CVE queries (auto-paginate all pages); stop conditions applied |
| `efficient-counting` [PREFERRED] | Not directly triggered (this is a listing, not a "how many" question), but counting approach available if user follows up with "how many" |
| `error-handling` [PREFERRED] | Oversized result retry strategy, HTTP error interpretation, empty vs. error distinction |
| `response-formatting` [GUIDANCE] | Table format for hosts + CVEs, severity-descending sort, 20-item cap with continuation offer, summary paragraph for mixed results |
