# Eval 1: Counting + Multi-Step Workflow (With Skills)

## User Query

> "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Analysis

This query has two parts that require a multi-step workflow combining the **efficient-counting**, **multi-step-workflows**, **tool-invocation-rules**, **pagination-handling**, **response-formatting**, and **guardrails-safety** skills:

1. **Count**: "How many critical CVEs with known exploits are affecting my RHEL 8 systems?" — a counting question scoped to a specific RHEL version.
2. **Top 5 details**: "Show me the top 5 most severe ones with details" — a detail-retrieval request for the highest-severity subset.

### Key Skill Interactions

- **efficient-counting** dictates using `limit=1` + metadata for the count, never fetching all pages.
- **multi-step-workflows** identifies this as a cross-service query: RHEL 8 systems come from Vulnerability/Inventory, CVEs come from the Vulnerability service, and the two must be correlated.
- **tool-invocation-rules** specifies exact parameter names, types (string-typed booleans for `known_exploit`), impact code `"7"` for Critical, and the recommendation to include `advisory_available="true"` and `sort="-cvss_score"` by default.
- **guardrails-safety** requires extra emphasis on CVEs with `known_exploit=true` and transparency about data scope.
- **response-formatting** prescribes a table with CVE ID, Synopsis, Severity, CVSS Score, Affected Systems, and Remediation Available columns, sorted by severity descending.

---

## Step-by-Step Tool Call Plan

### Step 1: Count critical CVEs with known exploits (efficient counting)

**Goal**: Get the total count of critical CVEs with known exploits affecting the user's infrastructure. Per the **efficient-counting** skill, use `limit=1` and read `meta.total_items` — one API call, no data transfer.

**Tool call**:
```
tool: vulnerability__get_cves
args: {
  "limit": 1,
  "offset": 0,
  "impact": "7",
  "known_exploit": "true",
  "advisory_available": "true"
}
```

**Reasoning**:
- `impact="7"` filters to Critical severity only (per **tool-invocation-rules**: `"7"` = Critical).
- `known_exploit="true"` is passed as a **string**, not a JSON boolean — this is a string-typed boolean per the **tool-invocation-rules** skill's "String-typed booleans — CRITICAL" section. Passing `true` (JSON boolean) would cause a tool call rejection.
- `advisory_available="true"` restricts to actionable CVEs with available advisories (recommended default per **tool-invocation-rules**).
- `limit=1` means we only fetch 1 record but get the full count from `meta.total_items` — per the **efficient-counting** skill, this is the correct approach for any "how many" question.
- This gives a global count across all the user's systems (not RHEL-8-only). The Vulnerability service scopes results to the user's registered infrastructure via JWT, but does not offer a RHEL version filter on `vulnerability__get_cves`. Step 2 addresses the RHEL 8 scoping.

**Expected response metadata**:
```json
{
  "meta": {
    "total_items": <count>,
    "offset": 0,
    "limit": 1
  }
}
```

Read `meta.total_items` to report: "There are N critical CVEs with known exploits and available advisories affecting your infrastructure."

---

### Step 2: Identify RHEL 8 systems (multi-step scoping)

**Goal**: Retrieve the list of RHEL 8 systems tracked for vulnerability analysis. Per the **multi-step-workflows** skill, this requires using `vulnerability__get_systems` (which has the `rhel_versions` filter), not `inventory__list_hosts` (which does not filter by RHEL version directly).

**Tool call (2a — count RHEL 8 systems)**:
```
tool: vulnerability__get_systems
args: {
  "rhel_versions": "8",
  "limit": 1,
  "offset": 0
}
```

**Reasoning**:
- Per the **multi-step-workflows** tool disambiguation table, `vulnerability__get_systems` is the correct tool for vulnerability-scoped system queries. It returns only systems tracked for CVE analysis (excludes immutable/edge systems).
- `rhel_versions="8"` filters to RHEL 8 systems.
- `limit=1` uses the **efficient-counting** approach to get the total RHEL 8 system count from metadata without fetching all data.

Read `meta.total_items` to know how many RHEL 8 systems exist.

**Tool call (2b — retrieve RHEL 8 system UUIDs)**:
```
tool: vulnerability__get_systems
args: {
  "rhel_versions": "8",
  "limit": 20,
  "offset": 0,
  "sort": "display_name"
}
```

**Reasoning**:
- We need the actual system UUIDs to correlate with CVE data in subsequent steps.
- `limit=20` fetches a manageable batch of system identifiers. If more exist, pagination can continue (per the **pagination-handling** skill, stop conditions apply).
- We collect the `system_uuid` values from the response `data` array for use in Steps 4-5.

---

### Step 3: Fetch the top 5 critical CVEs with known exploits (detail retrieval)

**Goal**: Get the 5 most severe critical CVEs with known exploits, including full details for the user's second question.

**Tool call**:
```
tool: vulnerability__get_cves
args: {
  "limit": 5,
  "impact": "7",
  "known_exploit": "true",
  "advisory_available": "true",
  "sort": "-cvss_score"
}
```

**Reasoning**:
- `limit=5` because the user asked for the top 5 — per **pagination-handling**, "Show me the top 5" means use `limit=5`, no follow-up offer needed.
- `sort="-cvss_score"` sorts by CVSS score descending to surface the most severe first — per **tool-invocation-rules**, always include `sort` for "top" or severity queries.
- `impact="7"` + `known_exploit="true"` + `advisory_available="true"` maintain the same filters as Step 1.
- The response `data` array contains CVE objects with fields like `id` (CVE ID), `attributes.description` (synopsis), `attributes.impact` (severity label), `attributes.cvss3_score` (CVSS score), `attributes.systems_affected` (count), `attributes.advisory_available` (remediation status), and `attributes.known_exploit` (exploit status).

**Data extracted per CVE**:
- CVE ID (e.g., `CVE-2024-XXXXX`)
- Synopsis/description
- Severity (Critical — confirmed by impact filter)
- CVSS score
- Number of affected systems
- Whether remediation/advisory is available
- Known exploit status (all `true` per filter, but worth confirming)

---

### Step 4: Get affected systems for each top CVE (cross-reference with RHEL 8)

**Goal**: For each of the 5 CVEs from Step 3, determine which specific RHEL 8 systems are affected. This is the key cross-referencing step in the multi-step workflow.

**Tool calls** (one per CVE — per **tool-invocation-rules**: "Each tool call performs exactly one action"):

```
tool: vulnerability__get_cve_systems
args: {
  "cve": "CVE-2024-XXXXX",
  "limit": 20,
  "sort": "display_name"
}
```

Repeat for each of the 5 CVE IDs returned in Step 3 (5 total calls).

**Reasoning**:
- Per **tool-invocation-rules**, the parameter is `cve` (not `cve_id`), and it must be uppercase format `"CVE-YYYY-NNNNN"`.
- `limit=20` provides a reasonable first page of affected systems.
- The response includes system display names and UUIDs, which we cross-reference against the RHEL 8 system UUIDs collected in Step 2b.
- Systems that appear in both this response AND the Step 2b RHEL 8 list are confirmed RHEL 8 systems affected by this CVE.
- Per **guardrails-safety**, CVEs with `known_exploit=true` "deserve extra emphasis regardless of severity label" — since all of these are Critical AND have known exploits, this warrants strong emphasis on urgency in the final presentation.

---

### Step 5: Get host details for key affected RHEL 8 systems (optional enrichment)

**Goal**: Provide additional context for the most important affected RHEL 8 systems — OS version, last check-in, system profile.

**Tool calls** (for selected systems from Step 4):

```
tool: inventory__get_host_system_profile
args: {
  "host_ids": "<uuid1>,<uuid2>"
}
```

**Reasoning**:
- Per **tool-invocation-rules**, `host_ids` takes comma-separated UUIDs, **one or two at a time** due to large response size.
- This confirms the exact RHEL 8.x minor version (e.g., RHEL 8.9 vs 8.6) and provides system profile details.
- Per **guardrails-safety**, check the `last_seen`/`updated` timestamp — if older than 24 hours, note that the information may be outdated.
- This step is optional but enhances the response quality for the user's "with details" request.

---

## Response Composition

Per the **response-formatting** skill, the final response would be structured as:

### Opening Summary

A brief summary paragraph stating:
- Total count of critical CVEs with known exploits (from Step 1 `meta.total_items`)
- Number of RHEL 8 systems in the environment (from Step 2a)
- Extra emphasis on the known-exploit status per **guardrails-safety**: "These CVEs have confirmed known exploits in the wild, which warrants prioritized remediation regardless of other factors."

### Top 5 CVE Table

Per **response-formatting**, use a table with these columns, sorted by severity (CVSS score) descending:

| CVE ID | Synopsis | Severity | CVSS Score | Affected RHEL 8 Systems | Remediation Available |
|--------|----------|----------|------------|------------------------|-----------------------|
| CVE-2024-XXXXX | Description from API | Critical | 9.8 | 12 of 45 | Yes |
| CVE-2024-YYYYY | Description from API | Critical | 9.6 | 8 of 45 | Yes |
| ... | ... | ... | ... | ... | ... |

The "Affected RHEL 8 Systems" column shows the count of RHEL 8 systems specifically (from Step 4 cross-reference), not the total affected systems across all RHEL versions.

### Scope Qualification

Per **guardrails-safety** (partial data transparency):
- Note that the total count from Step 1 covers all the user's systems, not just RHEL 8 — if the cross-referenced RHEL-8-specific count differs, state both clearly.
- If the RHEL 8 system list was paginated (more than 20 systems), note: "Showing affected systems from the first 20 of N RHEL 8 systems. Would you like me to check additional systems?"

### Actionable Guidance

Per **guardrails-safety** (read-only scope):
- Emphasize urgency for Critical + known-exploit CVEs.
- Note which CVEs have advisories/remediations available.
- Clarify that the agent operates in read-only mode — "Applying patches is done through your normal change management process. I can provide more details on any specific CVE or affected system to support your remediation planning."

---

## Summary of All Tool Calls

| Step | Tool | Key Arguments | Purpose | Skill(s) Applied |
|------|------|--------------|---------|-------------------|
| 1 | `vulnerability__get_cves` | `limit=1, impact="7", known_exploit="true", advisory_available="true"` | Count critical CVEs with known exploits | efficient-counting, tool-invocation-rules |
| 2a | `vulnerability__get_systems` | `rhel_versions="8", limit=1` | Count RHEL 8 systems | efficient-counting, multi-step-workflows |
| 2b | `vulnerability__get_systems` | `rhel_versions="8", limit=20, sort="display_name"` | Get RHEL 8 system UUIDs for cross-reference | multi-step-workflows, tool-invocation-rules |
| 3 | `vulnerability__get_cves` | `limit=5, impact="7", known_exploit="true", advisory_available="true", sort="-cvss_score"` | Fetch top 5 CVE details | tool-invocation-rules, pagination-handling |
| 4 (x5) | `vulnerability__get_cve_systems` | `cve="CVE-...", limit=20, sort="display_name"` | Get affected systems per CVE | multi-step-workflows, tool-invocation-rules |
| 5 (optional) | `inventory__get_host_system_profile` | `host_ids="<uuid1>,<uuid2>"` | Enrich with system profile details | tool-invocation-rules, guardrails-safety |

**Total tool calls**: 4 fixed + 5 per-CVE + optional enrichment = **9-11 calls**

Steps 1, 2a, and 2b could potentially be issued in parallel since they have no data dependencies on each other. Steps 3 depends on nothing from Steps 1-2 in terms of arguments (same filters), so it could also run in parallel with Steps 1-2. Steps 4 depends on Step 3 (needs CVE IDs). Step 5 depends on Steps 2b and 4 (needs system UUIDs cross-referenced).

---

## Error Handling Considerations

Per the **error-handling** skill:
- If any tool call returns `tool_result_too_large`, reduce `limit` (e.g., from 20 to 10) and retry automatically — do not tell the user the tool failed.
- If a tool returns HTTP 401/403, tell the user to re-authenticate or check RBAC permissions.
- If Step 4 returns empty results for a CVE (no affected systems), report it as a finding: "CVE-XXXX does not currently affect any of your registered systems."
- If the MCP server is unreachable, retry once, then report the backend is unavailable.
