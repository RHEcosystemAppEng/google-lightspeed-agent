# Evaluation Response: Critical CVEs with Known Exploits on RHEL 8 Systems

## User Query

> "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

## Analysis

This query has two distinct parts:

1. **A counting question**: "How many critical CVEs with known exploits are affecting my RHEL 8 systems?"
2. **A detail-retrieval question**: "Show me the top 5 most severe ones with details."

This is a multi-step workflow that combines counting (efficient-counting skill) with detail retrieval (multi-step-workflows skill). The query involves both the Vulnerability and potentially the Inventory services.

## Step-by-Step Tool Call Plan

### Step 1: Get the count of critical CVEs with known exploits affecting my systems

**Reasoning**: The user asks "how many" — this is a counting question. Per the **efficient-counting** skill, I should use `limit=1` and read `meta.total_items` from the response metadata rather than fetching all pages. The **tool-invocation-rules** skill confirms that `vulnerability__get_cves` supports `severity`, `known_exploit`, and `affecting` as filter parameters. Since the user is asking about CVEs "affecting my systems" (not a specific host), `vulnerability__get_cves` is the correct tool per the **multi-step-workflows** skill's CVE query disambiguation — no specific system is named, so the global CVE list with `affecting=true` is appropriate.

Note: The user specifies "RHEL 8 systems" but `vulnerability__get_cves` does not have an OS filter parameter in the confirmed parameter list. The `affecting=true` flag restricts results to CVEs affecting at least one of the user's systems, but cannot filter by OS version at this level. I will address the RHEL 8 scoping after getting the initial count.

```
tool: vulnerability__get_cves
args: {
  "limit": 1,
  "severity": "Critical",
  "known_exploit": true,
  "affecting": true
}
```

**Expected output**: Response with `meta.total_items` giving the total count of critical CVEs with known exploits affecting the user's systems.

**What I report**: "There are [N] critical CVEs with known exploits currently affecting your systems."

### Step 2: Identify RHEL 8 systems in the user's inventory

**Reasoning**: To scope this specifically to RHEL 8 (as the user requested), I need to identify which of their systems run RHEL 8. Per the **multi-step-workflows** skill, `inventory__list_hosts` is the tool for listing systems, and the **tool-invocation-rules** skill confirms it supports the `operating_system` filter parameter. I'll first get a count using efficient counting, and then fetch enough to get system IDs for cross-referencing.

```
tool: inventory__list_hosts
args: {
  "limit": 1,
  "operating_system": "RHEL 8"
}
```

**Expected output**: Response with `total` giving the number of RHEL 8 systems. This also confirms the user has RHEL 8 systems.

### Step 3: Fetch the top 5 critical CVEs with known exploits (with details)

**Reasoning**: The user wants the "top 5 most severe" with details. Per the **tool-invocation-rules** skill, I should use `sort=-cvss_score` to get the most severe first, and `limit=5` since the user asked for exactly 5. I keep the same filters from Step 1 to maintain consistency. Per the **pagination-handling** skill, since the user specified a quantity (5), no follow-up pagination offer is needed.

```
tool: vulnerability__get_cves
args: {
  "limit": 5,
  "severity": "Critical",
  "known_exploit": true,
  "affecting": true,
  "sort": "-cvss_score"
}
```

**Expected output**: Up to 5 CVE records with full details including CVE ID, CVSS score, description, affected system count, remediation availability, and known exploit status.

### Step 4: For each of the top 5 CVEs, get affected systems (scoped to RHEL 8)

**Reasoning**: To answer the RHEL 8 scoping part and provide complete details, I need to check which specific systems are affected by each CVE. Per the **multi-step-workflows** skill, `vulnerability__get_cve_systems` can retrieve the systems affected by a specific CVE. Per the **tool-invocation-rules** skill, one action per call — so I make one call per CVE. I can then cross-reference the affected systems against the RHEL 8 systems identified in Step 2.

For each CVE returned in Step 3 (up to 5 calls):

```
tool: vulnerability__get_cve_systems
args: {
  "cve_id": "<CVE-ID-from-step-3>"
}
```

**Expected output**: List of systems affected by each CVE, which I can cross-reference with the RHEL 8 host list to confirm RHEL 8 impact.

### Step 5: Present the results

**Reasoning**: Per the **response-formatting** skill, CVE lists should be presented as a table with columns for CVE ID, Severity, Affected Systems, and Remediation Available, sorted by severity descending. Per the **guardrails-safety** skill, I should emphasize CVEs with `known_exploit=true` and note that critical CVEs with known exploits warrant urgent attention. I should also note the RHEL 8 scoping caveat transparently per the partial data transparency guidelines.

**Expected formatted response**:

1. Lead with the total count from Step 1.
2. Note how many RHEL 8 systems were found in Step 2.
3. Present the top 5 CVEs in a table:

| CVE ID | CVSS Score | Severity | Affected RHEL 8 Systems | Remediation Available | Known Exploit |
|--------|-----------|----------|------------------------|----------------------|---------------|
| CVE-XXXX-XXXXX | 9.8 | Critical | 12 | Yes | Yes |
| ... | ... | ... | ... | ... | ... |

4. For each CVE, provide a brief description and remediation guidance.
5. Note that the agent operates in read-only mode — applying patches should be done through the user's normal change management process (per guardrails-safety skill).
6. Flag that these are known-exploit CVEs and emphasize urgency for production systems.

## Summary of Tool Calls

| Step | Tool | Key Arguments | Purpose |
|------|------|---------------|---------|
| 1 | `vulnerability__get_cves` | `limit=1, severity=Critical, known_exploit=true, affecting=true` | Get total count (efficient counting) |
| 2 | `inventory__list_hosts` | `limit=1, operating_system=RHEL 8` | Count and identify RHEL 8 systems |
| 3 | `vulnerability__get_cves` | `limit=5, severity=Critical, known_exploit=true, affecting=true, sort=-cvss_score` | Fetch top 5 most severe CVE details |
| 4 | `vulnerability__get_cve_systems` (x5) | `cve_id=<each CVE ID>` | Get affected systems per CVE for RHEL 8 cross-reference |

**Total tool calls**: 8 (1 count + 1 inventory + 1 detail fetch + 5 per-CVE system lookups)

## Skills Applied

- **efficient-counting**: Used `limit=1` + metadata for the count in Steps 1 and 2 instead of fetching all pages.
- **multi-step-workflows**: Chained Vulnerability and Inventory tools to build a complete answer; used correct tool disambiguation (global `vulnerability__get_cves` since no specific host was named).
- **tool-invocation-rules**: Used confirmed filter parameters (`severity`, `known_exploit`, `affecting`, `sort`, `operating_system`); passed arguments as native JSON types; one action per call for per-CVE system lookups.
- **pagination-handling**: User specified "top 5" so `limit=5` is used with no pagination follow-up needed.
- **response-formatting**: Results presented as a table sorted by severity/CVSS score with summary line and actionable context.
- **guardrails-safety**: Emphasized known-exploit urgency; noted read-only mode for remediation; transparent about RHEL 8 filtering limitations at the global CVE level.
- **error-handling**: Ready to handle `tool_result_too_large` by reducing limit, and to distinguish empty results (good news: zero critical CVEs) from API failures.
