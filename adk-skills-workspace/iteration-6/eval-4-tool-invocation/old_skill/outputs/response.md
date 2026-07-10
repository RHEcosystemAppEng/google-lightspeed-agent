# Tool Invocation Plan: "Show me the top critical and important CVEs affecting my systems"

## Analysis of the Request

The user wants to see CVEs filtered by two severity levels (Critical and Important) that are actively affecting their systems. This requires careful handling because:

1. The `severity` parameter on `vulnerability__get_cves` accepts **exactly one value** — not a list or comma-separated string (per the tool-invocation-rules skill).
2. The user wants CVEs that are actually **affecting** their systems, not the entire global CVE database.
3. The user asks for "top" CVEs, implying they want the most severe ones first.

## Strategy Selection

The tool-invocation-rules skill provides two strategies for multi-severity queries:

1. **Preferred — sort by score**: Omit `severity` and use `sort=-cvss_score`. The top results will naturally be Critical and Important.
2. **Separate calls**: Make one call per severity and merge the results.

I will use **Strategy 1 (sort by score)** because:
- It is explicitly marked as "Preferred" in the skill instructions.
- Sorting by CVSS score descending naturally surfaces Critical and Important CVEs first.
- It requires fewer tool calls (one instead of two).
- The multi-step-workflows skill confirms this approach: its workflow example for "What are the most critical vulnerabilities on my systems?" uses `sort=-cvss_score` without a `severity` filter.

## Step-by-Step Tool Invocation Plan

### Step 1: Fetch the top CVEs affecting the user's systems

**Tool:** `vulnerability__get_cves`
**Arguments:**
```json
{
  "limit": 20,
  "sort": "-cvss_score",
  "affecting": true
}
```

**Reasoning:**
- `sort=-cvss_score`: Orders results by CVSS score descending, so Critical (CVSS 9.0-10.0) and Important (CVSS 7.0-8.9) CVEs appear first. This is the preferred strategy from the tool-invocation-rules skill for multi-severity queries.
- `affecting=true`: Restricts results to only CVEs that affect at least one of the user's registered systems, as specified in both the tool-invocation-rules and multi-step-workflows skills.
- `limit=20`: Fetches a reasonable first page (the pagination-handling skill recommends 20 for CVE lists as a sensible default). This gives enough results to show the top Critical and Important CVEs.
- `severity` is intentionally **omitted** because it only accepts a single value, and the user wants both Critical and Important.

### Step 2: Examine the response and check pagination metadata

After receiving the response, I would:
- Read `meta.total_items` to know how many total CVEs match the query (affecting the user's systems).
- Read `meta.limit` and `meta.offset` to understand pagination state.
- Check if the returned results include both Critical and Important CVEs.

Per the pagination-handling skill: "After receiving the response, check the total count from the metadata. If significantly more data exists, tell the user the total and offer to fetch more."

### Step 3: For the top CVEs, get affected system details (optional enrichment)

For the most critical CVEs returned (e.g., the top 3-5), I would retrieve which specific systems are affected:

**Tool:** `vulnerability__get_cve_systems`
**Arguments (per CVE):**
```json
{
  "cve_id": "CVE-YYYY-XXXXX"
}
```

**Reasoning:**
- The multi-step-workflows skill's example workflow says: "for top CVEs, `vulnerability__get_cve_systems` -> cross-reference with `inventory__get_host_details` for system context -> synthesize prioritized report."
- This tells the user not just *what* CVEs exist, but *which systems* are affected — making the response actionable.
- Per the tool-invocation-rules skill, each tool call performs exactly one action, so I would make one call per CVE.

### Step 4: Get host details for affected systems (optional deeper enrichment)

For the systems identified in Step 3, I could optionally retrieve more context:

**Tool:** `inventory__get_host_details`
**Arguments:**
```json
{
  "host_id": "<system-id-from-step-3>"
}
```

**Reasoning:**
- Provides system context such as display name, OS version, and last check-in time.
- The response-formatting skill specifies including "Display Name, OS, Last Check-in" for host data.
- The guardrails-safety skill notes: "When presenting host data, note the `last_seen`/`updated` timestamp if it's older than 24 hours."

## Response Formatting

Per the response-formatting skill, the final answer would be presented as:

1. **Summary paragraph**: Brief overview of findings (e.g., "I found X Critical and Y Important CVEs affecting your systems").
2. **CVE table** with columns: CVE ID, Severity, CVSS Score, Affected Systems count, Remediation Available (Yes/No), sorted by severity descending.
3. **Pagination note**: If more CVEs exist beyond the 20 shown, state the total and offer to fetch more or apply additional filters.
4. **Known exploit emphasis**: Per the guardrails-safety skill, any CVE with `known_exploit=true` would receive extra emphasis regardless of severity level.

## Error Handling Considerations

Per the error-handling skill:
- If `vulnerability__get_cves` returns `tool_result_too_large`, I would retry with a reduced `limit` (e.g., 10) or add `severity=Critical` to narrow results.
- If the API returns empty results, I would frame it as a positive finding: "No critical or important CVEs were found affecting your systems."
- If a tool call fails with a 500/502/503, I would retry once before reporting the service as temporarily unavailable.

## Summary of Tool Calls

| Step | Tool | Key Arguments | Purpose |
|------|------|---------------|---------|
| 1 | `vulnerability__get_cves` | `limit=20, sort=-cvss_score, affecting=true` | Get top CVEs by severity affecting the user's systems |
| 2 | *(inspect response metadata)* | — | Check total count, pagination state |
| 3 | `vulnerability__get_cve_systems` | `cve_id=<each top CVE>` | Identify which systems each top CVE affects |
| 4 | `inventory__get_host_details` | `host_id=<system-id>` | Get system context (name, OS, last check-in) |

Steps 3 and 4 are enrichment steps that provide actionable detail. The core answer comes from Step 1. The number of calls in Steps 3-4 depends on how many top CVEs the user wants to drill into.
