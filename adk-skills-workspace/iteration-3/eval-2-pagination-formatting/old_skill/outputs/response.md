# Eval 2: "List all my hosts that have remediatable vulnerabilities. I want to prioritize patching."

## Plan and Step-by-Step Tool Calls

This query requires a multi-step workflow (per the **multi-step-workflows** skill) because it crosses two service domains: we need to identify systems from the Vulnerability service and then retrieve their remediatable CVEs to enable prioritization. The user wants to prioritize patching, so we need severity, exploit status, and remediation availability.

---

### Step 1: Get the list of systems tracked for vulnerability analysis

**Reasoning:** The user is asking about vulnerabilities, so per the **multi-step-workflows** skill's tool disambiguation rule, we use `vulnerability__get_systems` (systems tracked for CVE analysis) rather than `inventory__list_hosts` (full fleet including immutable/edge systems that aren't relevant to patching).

We start with a reasonable default page size per the **pagination-handling** skill ("fetch first, ask later" with a sensible default).

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 0}
```

**After receiving the response**, check `meta.total_items` to understand the fleet size. For example, if the response shows `meta.total_items: 230`, we know there are 230 systems total and we received the first 50.

---

### Step 2: Paginate through remaining systems (if needed)

**Reasoning:** Per the **pagination-handling** skill, we need to fetch all systems to give the user a complete picture. We advance `offset` by the `limit` value each time and apply the stop conditions.

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 50}
```

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 100}
```

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 150}
```

```
tool: vulnerability__get_systems
args: {"limit": 50, "offset": 200}
```

**Stop conditions** (per the **pagination-handling** skill, whichever applies first):
1. `links.next` is `null`, or
2. The next `offset` would be >= `meta.total_items`, or
3. `data` has fewer elements than `limit` (last partial page) or is empty.

In this example, page 5 (offset=200) returns 30 items (fewer than limit=50), so we stop.

---

### Step 3: For each system, query remediatable CVEs sorted by severity

**Reasoning:** The user specifically wants "remediatable vulnerabilities" and wants to "prioritize patching." Per the **pagination-handling** skill's exception rule: "When the user asks for remediatable CVEs on a specific system, fetch all pages automatically. Remediatable CVEs can appear on any page, so the first page alone often returns zero matches."

Per the **tool-invocation-rules** skill, `vulnerability__get_system_cves` supports `remediation` (value: `Applicable`) and `sort` parameters. We sort by severity to support prioritization.

For each system ID collected in Steps 1-2:

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 0, "remediation": "Applicable", "sort": "-cvss_score"}
```

**Handling pagination within each system's CVEs:** Per the pagination-handling skill's exception for remediatable CVE queries, we fetch ALL pages automatically for each system. If `meta.total_items` > 20, continue:

```
tool: vulnerability__get_system_cves
args: {"limit": 20, "offset": 20, "remediation": "Applicable", "sort": "-cvss_score"}
```

Continue until a stop condition is met.

**Error handling (per the error-handling skill):** If any call returns `tool_result_too_large`, reduce `limit` from 20 to 10 and retry. If a 500/502/503 occurs, retry once. If 401/403, report a permissions issue for that system.

---

### Step 4: Synthesize and present prioritized results

**Reasoning:** Per the **response-formatting** skill, CVE lists should use a table format sorted by severity descending. Per the **guardrails-safety** skill, CVEs with `known_exploit=true` deserve extra emphasis regardless of severity label.

**Presentation approach:**

1. **Summary paragraph** — total systems with remediatable vulnerabilities, total unique remediatable CVEs found, breakdown by severity.

2. **Prioritized table of systems** — sorted by number of Critical/Important remediatable CVEs:

| Host | OS | Critical | Important | Moderate | Low | Total Remediatable |
|---|---|---|---|---|---|---|
| prod-web-01.example.com | RHEL 8.9 | 3 | 7 | 12 | 5 | 27 |
| prod-db-02.example.com | RHEL 9.2 | 2 | 4 | 8 | 3 | 17 |
| ... | ... | ... | ... | ... | ... | ... |

3. **Top CVEs to address first** — unique CVEs across all systems, sorted by CVSS score:

| CVE ID | Severity | CVSS | Known Exploit | Affected Systems | Remediation Available |
|---|---|---|---|---|---|
| CVE-2024-XXXX | Critical | 9.8 | Yes | 15 | Yes |
| CVE-2024-YYYY | Critical | 9.1 | No | 8 | Yes |
| ... | ... | ... | ... | ... | ... |

4. **Pagination transparency** (per the **guardrails-safety** skill): State the total and how many were retrieved, e.g., "Showing all 230 systems. 142 have at least one remediatable vulnerability."

5. **Inline list cap** (per the **response-formatting** skill): If more than 20 items in any table, show the first 20 and add: "...and 47 more. Ask me to continue or apply filters to narrow down."

6. **Read-only reminder** (per the **guardrails-safety** skill): Note that applying patches is done through the user's normal change management process — this agent provides analysis only.

---

## Pagination Handling Summary

| Phase | Tool | Page Size | Pagination Strategy |
|---|---|---|---|
| System listing | `vulnerability__get_systems` | 50 | Fetch all pages to get complete system list |
| Per-system CVEs | `vulnerability__get_system_cves` | 20 | Fetch all pages automatically (remediatable CVE exception) |

**Key pagination decisions:**

- **Systems**: Fetch all because the user said "all my hosts" — we need the complete list to give an accurate answer.
- **Per-system CVEs with remediation filter**: Fetch all pages automatically per the pagination-handling skill's exception rule for remediatable CVE queries. Remediatable CVEs can appear on any page, so stopping at page 1 would miss results.
- **Stop conditions**: Applied consistently — stop when `links.next` is null, next offset >= `meta.total_items`, or `data` length < `limit`.
- **Error recovery**: If `tool_result_too_large`, reduce page size from 20 to 10. If that still fails, add severity filter (e.g., `severity=Critical`) and iterate through severity levels.

## Potential Optimizations

- **For very large fleets (500+ systems):** Instead of querying CVEs per-system, we could first use `vulnerability__get_cves` with `affecting=true` and `remediation=Applicable` (if supported) to get the universe of remediatable CVEs, then use `vulnerability__get_cve_systems` per CVE. This inverts the query but may result in fewer total API calls if there are fewer unique CVEs than systems.
- **Efficient counting first:** Per the **efficient-counting** skill, we could start with `vulnerability__get_systems` with `limit=1` to get the total system count, then decide on page size accordingly. This gives us the fleet size with a single call before committing to full pagination.
