# Response: "List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

This is a multi-step workflow that requires combining Vulnerability and Inventory data. The user wants hosts with remediatable CVEs, prioritized for patching. Here is my step-by-step plan.

---

## Step 1: Get remediatable CVEs sorted by severity

**Tool:** `vulnerability__get_cves`
**Arguments:**
```json
{
  "advisory_available": "true",
  "sort": "-cvss_score",
  "limit": 20,
  "offset": 0
}
```

**Reasoning:** The user wants to prioritize patching, so I fetch CVEs that have advisories available (`advisory_available="true"` — string-typed boolean, not JSON boolean). I sort by `-cvss_score` descending to surface the most critical vulnerabilities first. I start with `limit=20` as a sensible default per the pagination-handling skill. The `advisory_available` filter ensures every CVE returned has a remediation path.

**After receiving the response**, I read `meta.total_items` to know the full count. If significantly more than 20 exist, I report: "Showing 20 of N remediatable CVEs sorted by severity. Would you like me to fetch more, or apply filters (e.g., Critical only) to narrow the results?"

---

## Step 2: For each top CVE, get affected systems

**Tool:** `vulnerability__get_cve_systems` (called once per CVE)
**Arguments (example for the first CVE):**
```json
{
  "cve": "CVE-2024-XXXXX",
  "limit": 20,
  "offset": 0
}
```

**Reasoning:** Per the multi-step-workflows skill, I use `vulnerability__get_cve_systems` to find which specific hosts are affected by each high-severity CVE. The `cve` parameter requires the format `"CVE-YYYY-NNNNN"` (uppercase, and note: the parameter is named `cve`, not `cve_id`). I call this once per CVE from Step 1 — per the tool-invocation-rules skill, each tool call performs exactly one action; I do not try to batch multiple CVE IDs.

**Pagination handling:** After each call, I check `meta.total_items` and `links.next`. If there are more affected systems than the first page returns, I paginate through all pages by advancing `offset` by `limit` each time, stopping when:
- `links.next` is `null`, OR
- next `offset` >= `meta.total_items`, OR
- `data` has fewer elements than `limit` (partial last page) or is empty

This is important because remediatable systems can appear on any page.

---

## Step 3: Collect unique host UUIDs and get host details

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "per_page": 10,
  "page": 1,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

Or, if I already have specific host UUIDs from Step 2, I can look them up directly:

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "hostname_or_id": "<host-uuid>",
  "per_page": 10,
  "page": 1,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Reasoning:** Per the tool-invocation-rules skill, `inventory__list_hosts` uses `per_page` (integer, use 10 on first call) and `page` (starts at 1), with `order_by="display_name"` and `order_how="ASC"` for user-facing listings. I gather host details (display name, OS, last check-in) to enrich the output.

---

## Step 4: Synthesize and present a prioritized patching report

**Formatting (per response-formatting skill):**

I present a summary paragraph followed by a structured table. Since this combines CVE and host data (mixed results from multiple tools), I lead with a brief summary and then break into labeled sections.

**Example output structure:**

> You have **N** hosts affected by remediatable vulnerabilities. Here are your hosts prioritized by the severity of their most critical unpatched CVE:
>
> | Host | OS | Most Critical CVE | Severity | CVSS | Total Remediatable CVEs | Last Check-in |
> |---|---|---|---|---|---|---|
> | prod-web-01 | RHEL 9.3 | CVE-2024-12345 | Critical | 9.8 | 12 | 2 hours ago |
> | prod-db-02 | RHEL 8.9 | CVE-2024-23456 | Critical | 9.1 | 8 | 1 hour ago |
> | staging-app-01 | RHEL 9.2 | CVE-2024-34567 | Important | 7.5 | 5 | 3 hours ago |
> | ... | ... | ... | ... | ... | ... | ... |
>
> Showing 20 of 142 affected hosts. Would you like me to continue, or focus on a specific severity level or host group?

**Per the guardrails-safety skill**, I also:
- Note if any `last_seen` timestamps are older than 24 hours (stale data warning)
- Highlight CVEs with `known_exploit=true` for extra urgency regardless of severity label
- Clarify that I operate in read-only mode: "I can show you which systems need patching and prioritize them, but applying patches is done through your normal change management process."

---

## Handling Pagination for Large Environments

If the environment has hundreds or thousands of hosts with remediatable CVEs, I follow the pagination-handling skill:

1. **First pass:** Fetch the first page of remediatable CVEs (`limit=20`), check `meta.total_items`.
2. **Report total and offer options:** "There are 1,247 remediatable CVEs across your fleet. I've pulled the top 20 by severity. Would you like me to fetch more, or filter by Critical-only (`impact="7"`) to focus on the most urgent?"
3. **If the user wants all:** Paginate through all pages, advancing `offset` by `limit` each call, applying stop conditions (null `links.next`, offset >= total, empty/partial page).
4. **If `tool_result_too_large`:** Per the error-handling skill, I automatically retry with a smaller page size (e.g., reduce from 20 to 10), then add filters if still too large — I do not tell the user the tool failed.

---

## Alternative Efficient Approach

If the user primarily wants a count first ("how many hosts have remediatable vulnerabilities?"), I would use the efficient-counting skill:

**Tool:** `vulnerability__get_systems`
**Arguments:**
```json
{
  "limit": 1,
  "offset": 0
}
```

Read `meta.total_items` to get the total count of systems tracked for vulnerability analysis, then proceed with the detailed fetch only if the user wants the full list.

---

## Summary of Tool Call Sequence

| Step | Tool | Purpose |
|---|---|---|
| 1 | `vulnerability__get_cves` | Get remediatable CVEs sorted by severity (`advisory_available="true"`, `sort="-cvss_score"`) |
| 2 | `vulnerability__get_cve_systems` (per CVE) | Find which hosts are affected by each top CVE |
| 3 | `inventory__list_hosts` | Get host details (display name, OS, last check-in) for affected systems |
| 4 | (synthesis) | Combine data into a prioritized patching table, sorted by most critical CVE per host |

**Key skill applications:**
- **tool-invocation-rules**: String-typed booleans (`advisory_available="true"`), correct parameter names (`cve` not `cve_id`, `per_page` not `limit` for inventory), `per_page=10` on first inventory call, always include `sort` and `order_by`
- **pagination-handling**: Fetch first page, report total, offer to continue; apply stop conditions on multi-page fetches
- **efficient-counting**: Use `limit=1` + metadata for pure count queries
- **multi-step-workflows**: Chain Vulnerability and Inventory tools to build a complete answer
- **response-formatting**: Table format with severity, CVSS, affected systems; summary line for truncated results; mixed-result sections
- **error-handling**: Retry with smaller page size on `tool_result_too_large`; distinguish empty results from errors
- **guardrails-safety**: Read-only mode disclaimer; stale data warnings; highlight known exploits; present severity labels as-is from the API
