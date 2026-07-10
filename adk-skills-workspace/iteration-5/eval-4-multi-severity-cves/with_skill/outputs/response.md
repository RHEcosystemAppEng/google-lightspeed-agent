# Step-by-Step Plan: "Show me the top critical and important CVEs affecting my systems"

## Analysis

This query asks for CVEs at two severity levels (Critical and Important) that affect the user's registered systems, ranked by severity. Per the **multi-step-workflows** skill, no specific system is named, so the global CVE list tool (`vulnerability__get_cves`) is the correct starting point -- not the per-system variant. The **tool-invocation-rules** skill tells us that the `impact` parameter accepts comma-separated numeric IDs, enabling both severities in a single call.

---

## Step 1 -- Retrieve top Critical and Important CVEs

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
- **`impact="5,7"`**: The tool-invocation-rules skill specifies that `impact` uses numeric IDs: `"7"` for Critical, `"5"` for Important. Comma-separated values request both in a single call, avoiding two separate requests.
- **`sort="-cvss_score"`**: The tool-invocation-rules skill states to **always include sort for "top" or severity queries**. The `-` prefix sorts descending so the most severe CVEs appear first.
- **`advisory_available="true"`**: Per the multi-step-workflows skill, this should be included by default when no specific system is named, to restrict results to actionable CVEs (those with available advisories/patches). Note this is a **string-typed boolean** -- passed as `"true"`, not JSON `true`.
- **`limit=20`**: The response-formatting skill caps inline lists at 20 items. This provides a meaningful "top" list without overwhelming the user.

**Expected output:** A list of up to 20 CVEs with their IDs, synopses, CVSS scores, severity levels, and affected-system counts, plus `meta.total_items` giving the total number of Critical+Important CVEs across the environment.

---

## Step 2 -- (Conditional) Handle errors or oversized responses

If Step 1 returns a `tool_result_too_large` error, the **error-handling** skill prescribes retrying with a narrower query. I would:

1. First retry with a reduced limit:
   ```json
   {
     "impact": "5,7",
     "sort": "-cvss_score",
     "advisory_available": "true",
     "limit": 10
   }
   ```
2. If still too large, split into two calls -- one for Critical only (`impact="7"`, `limit=10`) and one for Important only (`impact="5"`, `limit=10`).
3. If that still fails, add a CVSS floor filter (`cvss_from=8.0`) to narrow further.

If Step 1 returns an HTTP error, I would follow the error-handling skill's status code table (e.g., 401/403 -> tell user to re-authenticate; 429 -> retry once; 500+ -> retry once then report unavailability).

If Step 1 returns an empty result, I would report that as a positive finding ("No Critical or Important CVEs with available advisories were found affecting your systems"), per the error-handling skill's guidance to distinguish empty results from errors.

---

## Step 3 -- Enrich top CVEs with affected-system details

For the top 3-5 most severe CVEs from Step 1, retrieve which specific systems are affected.

**Tool:** `vulnerability__get_cve_systems` (called once per CVE)

Example for the highest-scored CVE:
```json
{
  "cve": "CVE-2024-XXXXX",
  "limit": 10,
  "sort": "-display_name"
}
```

**Reasoning:**
- The multi-step-workflows skill instructs to cross-reference top CVEs with `vulnerability__get_cve_systems` to provide system context.
- The `cve` parameter requires the full CVE ID in `"CVE-YYYY-NNNNN"` format (uppercase), not `cve_id`, per the tool-invocation-rules skill.
- I limit this enrichment to the top 3-5 CVEs to keep the response focused and avoid excessive API calls. The one-action-per-call rule means each CVE requires a separate call.

**Expected output:** For each queried CVE, a list of affected systems with their display names and UUIDs.

---

## Step 4 -- Format and present the results

Per the **response-formatting** skill:

1. **Lead with a brief summary paragraph** stating the total count of Critical + Important CVEs (from `meta.total_items` in Step 1) and the top findings.

2. **Present a CVE table** with these columns:
   - CVE ID
   - Synopsis (brief description)
   - Severity (Critical / Important)
   - CVSS Score
   - Affected Systems (count)
   - Remediation Available (Yes/No)

   Sorted by severity descending (Critical first, then Important), then by CVSS score descending within each severity tier.

3. **For the top 3-5 enriched CVEs**, add a detail section listing the specific affected system names from Step 3.

4. **Cap at 20 items** in the main table. If `meta.total_items` exceeds 20, add: "...and N more. Ask me to continue or apply filters to narrow down."

5. **Provide actionable next steps**, such as:
   - "Would you like me to show remediation steps for any of these CVEs?"
   - "I can check if specific systems in your environment are affected."
   - "Would you like to filter by systems with known exploits?"

---

## Summary of Tool Calls

| Order | Tool | Key Arguments | Purpose |
|-------|------|---------------|---------|
| 1 | `vulnerability__get_cves` | `impact="5,7"`, `sort="-cvss_score"`, `advisory_available="true"`, `limit=20` | Get top Critical + Important CVEs in one call |
| 2 | `vulnerability__get_cve_systems` | `cve="CVE-..."`, `limit=10` (x3-5 calls) | Enrich top CVEs with affected system names |

**Total calls: 4-6** (1 global query + 3-5 per-CVE enrichment calls)

---

## Key Skill Applications

- **tool-invocation-rules (v1.5):** Used `impact="5,7"` (comma-separated numeric IDs) for multi-severity in one call; used `advisory_available="true"` as a string-typed boolean (not JSON `true`); included `sort="-cvss_score"` for a "top" query; used correct `cve` parameter name (not `cve_id`).
- **multi-step-workflows (v1.2):** Selected `vulnerability__get_cves` (global scope, no specific system named); included `advisory_available="true"` by default; chained with `vulnerability__get_cve_systems` for system-level enrichment.
- **efficient-counting (v1.1):** The total count of matching CVEs comes from `meta.total_items` in the Step 1 response -- no additional call needed.
- **error-handling (v1.1):** Prepared fallback strategies for oversized responses (reduce limit, split severities, add CVSS floor) and HTTP errors (status code table).
- **response-formatting (v1.1):** CVE table format with required columns, 20-item cap, summary paragraph lead, severity-descending sort, actionable follow-up suggestions.
