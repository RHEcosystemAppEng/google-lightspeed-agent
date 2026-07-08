# Evaluation Response: Critical CVEs with Known Exploits on RHEL 8 Systems

## User Query
"How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Analysis

This query has two parts:
1. **A counting question**: "How many critical CVEs with known exploits are affecting my RHEL 8 systems?"
2. **A detail/listing question**: "Show me the top 5 most severe ones with details."

This is a multi-step workflow that spans two API domains (Inventory + Vulnerability) and combines the efficient-counting skill with the multi-step-workflows skill. I also need the pagination-handling skill (the user explicitly asked for 5 results, so I use `limit=5` with no follow-up offer) and the tool-invocation-rules skill for correct parameter formatting.

---

## Step-by-Step Plan

### Step 1: Identify RHEL 8 systems in the inventory

**Reasoning:** Before I can query CVEs for RHEL 8 systems, I need to know which systems are running RHEL 8. The multi-step-workflows skill directs me to resolve identifiers first. The tool-invocation-rules skill confirms `inventory__list_hosts` supports the `operating_system` filter. I also need to know the total count of RHEL 8 systems for context, so I start with `limit=1` per the efficient-counting skill to get the total from metadata without transferring data.

```
tool: inventory__list_hosts
args: {"operating_system": "RHEL 8", "limit": 1}
```

**Expected output:** A response with `total` in the metadata telling me how many RHEL 8 systems exist. I note this count for context in my final response (e.g., "Across your 47 RHEL 8 systems...").

### Step 2: Get the count of critical CVEs with known exploits affecting my systems

**Reasoning:** Now I need the count of critical CVEs with known exploits. The efficient-counting skill says: for "how many" questions, call the tool with `limit=1` and read `meta.total_items` from the response. The tool-invocation-rules skill confirms that `vulnerability__get_cves` supports `severity`, `known_exploit`, and `affecting` as filter parameters. I use `affecting=true` to restrict to CVEs that actually affect at least one of my systems.

However, `vulnerability__get_cves` does not have an `operating_system` filter -- it returns CVEs across all tracked systems. To get CVEs specific to RHEL 8 systems only, I would need to query per-system CVEs. But first, let me get the overall count of critical CVEs with known exploits affecting any of my systems, since the Vulnerability service already scopes to the user's organization.

```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 1}
```

**Expected output:** Response with `meta.total_items` giving the total count of critical CVEs with known exploits affecting my systems. I report this number to the user.

**Note on RHEL 8 scoping:** The `vulnerability__get_cves` endpoint returns CVEs across all systems in the organization, not filtered by OS version. To get CVEs specific to RHEL 8 systems only, I would need to iterate through RHEL 8 hosts and query their individual CVEs. However, for the count, this aggregate is the most efficient starting point. If the user has a mixed fleet (RHEL 7, 8, 9), I should note that this count covers all systems, not just RHEL 8, and offer to drill down per-system if needed.

### Step 3: Fetch the top 5 most severe critical CVEs with known exploits

**Reasoning:** The user asked for the top 5 most severe. I use `limit=5` (the user specified the quantity, so per the pagination-handling skill, no follow-up offer is needed). I sort by `-cvss_score` descending to get the most severe first. The tool-invocation-rules skill confirms the `sort` parameter accepts `-cvss_score`.

```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 5, "sort": "-cvss_score"}
```

**Expected output:** A list of up to 5 CVE records, each containing CVE ID, CVSS score, severity, description, affected system count, and whether remediation is available. I also get `meta.total_items` confirming the total count from Step 2.

### Step 4: For each of the top 5 CVEs, get affected system details

**Reasoning:** The user asked for "details," and the multi-step-workflows skill says to cross-reference CVEs with system information to provide a complete picture. For each CVE returned in Step 3, I query which systems are affected using `vulnerability__get_cve_systems`. This tells the user not just *what* CVEs exist, but *where* they are in their environment. I keep `limit` reasonable (e.g., 5 systems per CVE) since this is a summary view.

For each CVE (e.g., CVE-2024-XXXX):

```
tool: vulnerability__get_cve_systems
args: {"cve_id": "CVE-2024-XXXX", "limit": 5}
```

**Expected output:** List of affected systems with display names, OS versions, and remediation status. If there are more than 5 affected systems, I report the total from the metadata per the pagination-handling skill (e.g., "Affects 23 systems; showing 5").

These 5 calls (one per CVE) can be made in parallel since they are independent.

### Step 5: Synthesize and present the response

**Reasoning:** The response-formatting skill directs me to present CVE lists as a table sorted by severity descending, with columns for CVE ID, Severity, Affected Systems, and Remediation Available. The guardrails-safety skill says to emphasize CVEs with `known_exploit=true` and note the urgency. I also follow the partial-data-transparency guidance to state the total vs. what I'm showing.

**Response structure:**

1. **Lead with the count answer**: "There are **N** critical CVEs with known exploits currently affecting your systems."
2. **Note RHEL 8 context**: Mention the number of RHEL 8 systems from Step 1 (e.g., "You have 47 RHEL 8 systems in your inventory").
3. **Table of top 5 CVEs**:

| CVE ID | CVSS Score | Severity | Known Exploit | Affected Systems | Remediation |
|--------|-----------|----------|---------------|-----------------|-------------|
| CVE-2024-AAAA | 9.8 | Critical | Yes | 23 systems | Available |
| CVE-2024-BBBB | 9.6 | Critical | Yes | 18 systems | Available |
| CVE-2024-CCCC | 9.4 | Critical | Yes | 12 systems | Not available |
| CVE-2024-DDDD | 9.1 | Critical | Yes | 8 systems | Available |
| CVE-2024-EEEE | 8.8 | Critical | Yes | 5 systems | Available |

4. **Per-CVE details**: For each CVE, list the top affected systems with their display names and OS versions.
5. **Actionable guidance**: Per the guardrails-safety skill, emphasize that known-exploit CVEs warrant faster action. Recommend prioritizing those with available remediations. Note that remediation itself must be done through the user's change management process (read-only mode per guardrails-safety).

---

## Skills Applied

| Skill | How It Was Applied |
|-------|-------------------|
| **efficient-counting** | Step 1 uses `limit=1` to count RHEL 8 systems via `total` metadata. Step 2 uses `limit=1` to count critical CVEs with known exploits via `meta.total_items`. No pagination needed for counting. |
| **multi-step-workflows** | The query spans Inventory (RHEL 8 systems) and Vulnerability (CVEs with known exploits). Steps are chained: identify systems first, then query CVEs, then cross-reference affected systems per CVE. |
| **tool-invocation-rules** | All tool calls use correct JSON argument types: `known_exploit` as boolean `true` (not string `"true"`), `limit` as integer `5` (not string `"5"`), `sort` as string `"-cvss_score"`. Parameters are confirmed available in the skill's known-parameters table. |
| **pagination-handling** | User specified "top 5", so `limit=5` is used directly with no offer to fetch more. For per-CVE system lists, the total is reported from metadata if more exist than shown. |
| **response-formatting** | Results presented as a table sorted by CVSS score descending. Columns include CVE ID, Severity, Affected Systems, and Remediation. Summary paragraph leads, followed by structured data. |
| **guardrails-safety** | Known-exploit CVEs are given extra emphasis. Severity labels are presented as-is from the API. The agent notes it operates in read-only mode -- remediation actions must go through normal change management. |
| **error-handling** | Not directly triggered in this plan, but if any tool call returns `tool_result_too_large`, the agent would reduce `limit` and retry. If a 404 or 403 is returned, the agent would report it transparently rather than guessing. |

---

## Summary of Tool Calls

| Step | Tool | Arguments | Purpose |
|------|------|-----------|---------|
| 1 | `inventory__list_hosts` | `{"operating_system": "RHEL 8", "limit": 1}` | Count RHEL 8 systems (read `total` from metadata) |
| 2 | `vulnerability__get_cves` | `{"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 1}` | Count critical CVEs with known exploits (read `meta.total_items`) |
| 3 | `vulnerability__get_cves` | `{"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 5, "sort": "-cvss_score"}` | Fetch top 5 most severe critical CVEs with known exploits |
| 4 | `vulnerability__get_cve_systems` | `{"cve_id": "<each CVE ID>", "limit": 5}` (x5 calls, parallelized) | Get affected systems for each of the top 5 CVEs |
| **Total** | | | **8 tool calls** (Steps 2 and 3 could be combined into one call with `limit=5`, reducing to **7 calls**) |

### Optimization Note

Steps 2 and 3 can be collapsed into a single call: Step 3 already uses `limit=5` and returns `meta.total_items`, which answers the counting question from Step 2. This reduces the total to **7 tool calls** (1 inventory + 1 CVE list + 5 per-CVE system lookups). The efficient-counting skill's `limit=1` approach is optimal when *only* a count is needed, but here the user also wants the top 5 details, so fetching 5 records and reading the total from the same response is strictly better.

**Optimized plan: 7 tool calls total.**
