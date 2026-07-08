# Evaluation Response: Critical CVEs with Known Exploits on RHEL 8 Systems

## User Query

> "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Analysis

This query has two parts:

1. **A counting question**: "How many critical CVEs with known exploits are affecting my RHEL 8 systems?"
2. **A detail request**: "Show me the top 5 most severe ones with details"

This is a **multi-step workflow** because it requires correlating data across Inventory (to identify RHEL 8 systems) and Vulnerability (to get CVE data). The Vulnerability API tools do not have an OS-level filter, so I cannot get "critical CVEs affecting only RHEL 8 systems" in a single call. I need to resolve the RHEL 8 systems first, then query their CVEs.

### Skills applied:
- **multi-step-workflows**: Chaining Inventory + Vulnerability tools to correlate OS with CVEs
- **efficient-counting**: Using `limit=1` + metadata for the count in Step 1
- **tool-invocation-rules**: Correct argument types and known filter parameters
- **pagination-handling**: Fetching system list if more than one page; using appropriate limits for detail queries
- **response-formatting**: Table format for CVE details, severity-descending sort
- **guardrails-safety**: Emphasizing known-exploit CVEs, noting data freshness

---

## Step-by-Step Plan

### Step 1: Count RHEL 8 systems in inventory

**Purpose**: Understand the scope — how many RHEL 8 systems does the user have? This also tells me whether I can feasibly query CVEs per-system or need a different strategy.

**Skill applied**: efficient-counting (limit=1 + metadata for count)

```
tool: inventory__list_hosts
args: {"operating_system": "RHEL 8", "limit": 1}
```

**What I read from the response**: The `total` field gives me the count of RHEL 8 systems. I also note how many systems there are to plan the next steps.

**Reasoning**: The multi-step-workflows skill says to use `inventory__list_hosts` for OS-based system queries. I start with `limit=1` per the efficient-counting skill because I only need the count first.

---

### Step 2: Fetch RHEL 8 system IDs

**Purpose**: Get the actual host IDs so I can query CVEs per system. I need these identifiers to call the per-system vulnerability tools.

**Skill applied**: pagination-handling (fetch first page with sensible default)

```
tool: inventory__list_hosts
args: {"operating_system": "RHEL 8", "limit": 20}
```

**What I read from the response**: The host UUIDs (IDs) and display names of the RHEL 8 systems. If `total` > 20, I would note that I'm working with the first 20 and offer to continue, per the pagination-handling skill.

**Reasoning**: I need the actual system IDs to query CVEs per system in the next step. The multi-step-workflows skill directs me to find systems first, then query their CVEs. I use `limit=20` as a sensible first page default per the pagination-handling skill.

---

### Step 3: Count critical CVEs with known exploits for each RHEL 8 system

**Purpose**: Answer the "how many" part of the question. For each RHEL 8 system from Step 2, I get the count of critical CVEs with known exploits.

**Skill applied**: efficient-counting (limit=1 + meta.total_items for each system)

For each system ID retrieved in Step 2, I call:

```
tool: vulnerability__get_system_cves
args: {"system_id": "<host-uuid-1>", "severity": "Critical", "known_exploit": true, "limit": 1}
```

```
tool: vulnerability__get_system_cves
args: {"system_id": "<host-uuid-2>", "severity": "Critical", "known_exploit": true, "limit": 1}
```

*(Repeated for each RHEL 8 system from Step 2)*

**What I read from each response**: `meta.total_items` — the count of critical CVEs with known exploits on that specific system. I aggregate across all systems, noting that the same CVE may appear on multiple systems (so I would deduplicate CVE IDs when reporting the total unique count).

**Reasoning**: The tool-invocation-rules skill specifies that `vulnerability__get_system_cves` supports `severity` and `known_exploit` as filter parameters. The efficient-counting skill says to use `limit=1` and read `meta.total_items`. The tool-invocation-rules skill says "one action per call" — I make separate calls per system. I report both the unique CVE count and the per-system breakdown.

---

### Step 4: Fetch top 5 most severe critical CVEs with known exploits (details)

**Purpose**: Answer the "show me the top 5" part. I pick the system with the highest count from Step 3 (or query multiple systems) and fetch details sorted by CVSS score.

**Skill applied**: tool-invocation-rules (sort parameter), response-formatting (table output)

```
tool: vulnerability__get_system_cves
args: {"system_id": "<host-uuid-with-most-cves>", "severity": "Critical", "known_exploit": true, "limit": 5, "sort": "-cvss_score"}
```

**What I read from the response**: The CVE ID, CVSS score, description, remediation availability, and number of affected systems for each of the top 5 CVEs.

**Reasoning**: I sort by `-cvss_score` (descending) to get the most severe first. The tool-invocation-rules skill confirms `sort` is a known parameter. I use `limit=5` since the user asked for the top 5.

If the user has many RHEL 8 systems and the top CVEs may differ across them, I could alternatively use the org-wide tool:

```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 5, "sort": "-cvss_score"}
```

This gets the top 5 critical CVEs with known exploits across the entire organization. I would then cross-reference each CVE against the RHEL 8 systems to confirm they are affected.

---

### Step 5 (conditional): Cross-reference top CVEs with RHEL 8 systems

**Purpose**: If I used the org-wide `vulnerability__get_cves` in Step 4, I need to verify which of the top CVEs actually affect RHEL 8 systems specifically (vs. other OS versions).

```
tool: vulnerability__get_cve_systems
args: {"cve_id": "CVE-2024-XXXX"}
```

*(Repeated for each of the top 5 CVEs)*

**What I read**: The list of affected systems for each CVE. I cross-reference these system IDs against the RHEL 8 host IDs from Step 2 to confirm they are RHEL 8 systems.

**Reasoning**: The multi-step-workflows skill says to cross-reference with inventory for system context. This ensures I'm only reporting CVEs that genuinely affect RHEL 8 systems, not other OS versions in the fleet.

---

## Expected Response Format

Per the response-formatting skill, I would present the results as:

1. **Summary line**: "Found **N** critical CVEs with known exploits affecting your **M** RHEL 8 systems."

2. **Top 5 table** (sorted by CVSS score descending):

| CVE ID | CVSS Score | Severity | Affected RHEL 8 Systems | Remediation Available | Description |
|--------|-----------|----------|------------------------|-----------------------|-------------|
| CVE-2024-XXXX | 9.8 | Critical | 12 | Yes | ... |
| CVE-2024-YYYY | 9.6 | Critical | 8 | Yes | ... |
| ... | ... | ... | ... | ... | ... |

3. **Known-exploit emphasis** (per guardrails-safety skill): "All 5 of these CVEs have confirmed known exploits in the wild, which means they should be prioritized for remediation regardless of other factors."

4. **Actionable next steps**: "Would you like me to show which specific RHEL 8 systems are affected by any of these CVEs, or check if remediations are available?"

---

## Error Handling Considerations

Per the error-handling skill:
- If any `vulnerability__get_system_cves` call returns `tool_result_too_large`, I would reduce `limit` (e.g., from 5 to 3) and retry.
- If a 404 is returned for a system ID, that system may have been deregistered — I report it and continue with remaining systems.
- If a 429 (rate limit) occurs during the per-system loop, I retry once after a pause.
- Empty results (zero critical CVEs with known exploits) are reported as a positive finding: "Good news — none of your RHEL 8 systems have critical CVEs with known exploits."

## Partial Data Transparency

Per the guardrails-safety skill:
- If there are more than 20 RHEL 8 systems and I only queried the first 20, I state: "Showing results for 20 of N RHEL 8 systems. Would you like me to continue checking the remaining systems?"
- I note the last check-in time for systems if it's older than 24 hours.
