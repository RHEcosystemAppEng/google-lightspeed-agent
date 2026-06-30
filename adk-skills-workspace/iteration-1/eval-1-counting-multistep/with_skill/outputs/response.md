# Eval 1: Counting + Multi-Step Workflow

**User query:** "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Analysis

This query has two distinct parts:

1. **A counting question** — "How many critical CVEs with known exploits are affecting my RHEL 8 systems?" This triggers the **efficient-counting** skill.
2. **A detail-retrieval question** — "Show me the top 5 most severe ones with details." This triggers the **multi-step-workflows** and **pagination-handling** skills (though with limit=5, pagination won't be needed beyond a single page).

The query also involves a cross-service join: "RHEL 8 systems" must be resolved via Inventory, then CVEs queried via the Vulnerability service for those systems. This is a textbook **multi-step workflow**.

---

## Step-by-Step Plan

### Step 1: Identify RHEL 8 systems (Inventory)

**Reasoning:** The user said "my RHEL 8 systems." To find CVEs affecting those systems, I first need to identify which systems are running RHEL 8. Per the **multi-step-workflows** skill, this is a cross-service query: Inventory gives me the host IDs, then Vulnerability gives me CVEs per host. Per the **tool-invocation-rules** skill, `inventory__list_hosts` supports `operating_system` as a known filter parameter.

**Tool call:**
```
tool: inventory__list_hosts
args: {"operating_system": "RHEL 8", "limit": 50, "offset": 0}
```

**Why limit=50:** Per the **pagination-handling** skill, I use a sensible default for host listings to get the first batch. I check the `total` metadata field to know how many RHEL 8 systems exist. If more than 50 exist, I would paginate — but for the counting + top-5 workflow, I need host IDs to query against, so I fetch enough to cover the fleet.

**What I extract:** The list of host UUIDs (from `results[].id`) and the total count of RHEL 8 systems (from `total`). If total > 50, I paginate to collect all host IDs.

---

### Step 2: Get the count of critical CVEs with known exploits (Efficient Counting)

**Reasoning:** The first part of the question is "how many." Per the **efficient-counting** skill, I should use `limit=1` and read `meta.total_items` — one API call, no data transfer. Per the **tool-invocation-rules** skill, `vulnerability__get_cves` supports `severity`, `known_exploit`, and `affecting` as confirmed parameters.

However, the user asks specifically about CVEs affecting their **RHEL 8 systems**, not all systems. There are two approaches:

- **Option A (per-system):** For each RHEL 8 host, call `vulnerability__get_system_cves` with `severity=Critical`, `known_exploit=true`, `limit=1` and read `meta.total_items`. This gives per-host counts but may double-count CVEs shared across hosts.
- **Option B (global + affecting):** Call `vulnerability__get_cves` with `severity=Critical`, `known_exploit=true`, `affecting=true`, `limit=1`. This gives the total count of critical CVEs with known exploits affecting **any** of the user's systems — but cannot filter to RHEL 8 only at the CVE-list level.

**Chosen approach: Option A** — query per system, since the user specifically asked about RHEL 8 systems. I call `vulnerability__get_system_cves` for each RHEL 8 host to get the accurate count scoped to those systems.

But first, I can get a quick **global count** as an upper bound:

**Tool call (global count, informational):**
```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 1, "offset": 0}
```

**What I extract:** `meta.total_items` — the total count of critical CVEs with known exploits affecting any of the user's systems. I report this alongside the RHEL-8-specific results for context.

Then, for each RHEL 8 system (using host IDs from Step 1), I call:

**Tool call (per RHEL 8 host, repeated for each host — but for efficiency, I do the detail query in Step 3 and derive the count from the same call):**

Since Step 3 needs the top 5 most severe CVEs with details anyway, I combine the counting and detail retrieval: I query for critical CVEs with known exploits on each RHEL 8 system, collect the results, deduplicate across hosts, and report both the count and the top 5.

---

### Step 3: Retrieve the top 5 most severe critical CVEs with known exploits on RHEL 8 systems

**Reasoning:** The user wants the "top 5 most severe ones with details." Per the **pagination-handling** skill, when the user specifies a quantity ("top 5"), I use `limit=5` and no follow-up offer is needed. Per the **tool-invocation-rules** skill, I can use `sort=-cvss_score` to sort by CVSS score descending.

For each RHEL 8 host ID from Step 1, I call:

**Tool call (repeated for each RHEL 8 host):**
```
tool: vulnerability__get_system_cves
args: {
  "inventory_id": "<host-uuid>",
  "severity": "Critical",
  "known_exploit": true,
  "sort": "-cvss_score",
  "limit": 5,
  "offset": 0
}
```

**What I extract per host:**
- `meta.total_items` — count of critical CVEs with known exploits on this specific RHEL 8 host (this answers the counting question from Step 2 per-host)
- `data[]` — the CVE details: CVE ID, CVSS score, severity, description, remediation status, known_exploit flag, affected systems count

**Cross-host deduplication:** After collecting results from all RHEL 8 hosts, I:
1. Deduplicate CVEs by CVE ID (same CVE may affect multiple RHEL 8 hosts)
2. Merge the affected-host lists per CVE
3. Sort the deduplicated set by CVSS score descending
4. Take the top 5

**Note on efficiency:** If the user has many RHEL 8 hosts (e.g., 200+), calling per-host would be expensive. In that case, I would:
- Use the global `vulnerability__get_cves` with `severity=Critical`, `known_exploit=true`, `affecting=true`, `sort=-cvss_score`, `limit=5` to get the top 5 CVEs across all systems
- Then for each of those 5 CVEs, call `vulnerability__get_cve_systems` to check which RHEL 8 hosts are affected
- This is more efficient: 1 + 5 = 6 calls vs. 200 calls

**Revised efficient approach for many hosts:**

**Tool call 3a (get top critical CVEs with known exploits globally):**
```
tool: vulnerability__get_cves
args: {
  "severity": "Critical",
  "known_exploit": true,
  "affecting": true,
  "sort": "-cvss_score",
  "limit": 5,
  "offset": 0
}
```

**What I extract:** `meta.total_items` (total count for the counting question), and the top 5 CVE records from `data[]` including CVE ID, CVSS score, description, severity, known_exploit status, affected system count.

**Tool call 3b (for each of the top 5 CVEs, get affected systems and cross-reference with RHEL 8 host list):**
```
tool: vulnerability__get_cve_systems
args: {
  "cve_id": "CVE-YYYY-XXXXX"
}
```

Repeated for each of the 5 CVEs. I then cross-reference the returned system IDs with the RHEL 8 host IDs from Step 1 to confirm which of these CVEs actually affect RHEL 8 systems specifically.

---

### Step 4: Format and present the response

**Reasoning:** Per the **response-formatting** skill, CVE lists should use a table with columns: CVE ID, Severity, Affected Systems, Remediation Available. Sort by severity descending. Per the **guardrails-safety** skill, CVEs with `known_exploit=true` deserve extra emphasis. Since this is a mixed result (counting + detail), I lead with a brief summary paragraph, then the table.

**Response structure:**

1. **Summary line:** "There are **N** critical CVEs with known exploits affecting your RHEL 8 systems (M systems total)."
2. **Emphasis on known exploits** (per guardrails-safety): "All of these CVEs have known exploits in the wild, which means they should be prioritized for remediation regardless of other factors."
3. **Table of top 5:**

| CVE ID | CVSS Score | Severity | Affected RHEL 8 Systems | Remediation Available |
|---|---|---|---|---|
| CVE-YYYY-XXXXX | 9.8 | Critical | 12 | Yes |
| ... | ... | ... | ... | ... |

4. **Actionable next steps:** Offer to show details for any specific CVE, list affected hosts for a particular CVE, or show remediatable CVEs.

---

## Summary of Tool Calls (Optimized Path)

| Step | Tool | Arguments | Purpose | Skill Applied |
|---|---|---|---|---|
| 1 | `inventory__list_hosts` | `operating_system="RHEL 8"`, `limit=50` | Identify RHEL 8 hosts | multi-step-workflows, tool-invocation-rules |
| 1b | `inventory__list_hosts` | `operating_system="RHEL 8"`, `limit=50`, `offset=50` | Paginate if >50 hosts | pagination-handling |
| 2 | `vulnerability__get_cves` | `severity="Critical"`, `known_exploit=true`, `affecting=true`, `limit=1` | Get total count | efficient-counting |
| 3a | `vulnerability__get_cves` | `severity="Critical"`, `known_exploit=true`, `affecting=true`, `sort="-cvss_score"`, `limit=5` | Get top 5 CVE details | pagination-handling, tool-invocation-rules |
| 3b | `vulnerability__get_cve_systems` | `cve_id="<cve-id>"` (x5) | Cross-reference with RHEL 8 hosts | multi-step-workflows |
| 4 | *(no tool call)* | *(formatting)* | Present results | response-formatting, guardrails-safety |

**Total tool calls:** 3 + pagination calls for hosts + 5 per-CVE system lookups = approximately **8-10 calls** in the optimized path.

---

## Skills Activated and How They Were Applied

1. **efficient-counting** [PREFERRED]: Used `limit=1` + `meta.total_items` in Step 2 to answer "how many" without fetching all pages.
2. **multi-step-workflows** [PREFERRED]: The query requires chaining Inventory (find RHEL 8 hosts) with Vulnerability (get CVEs for those hosts). This skill directed the cross-service workflow.
3. **tool-invocation-rules** [STRICT]: Used confirmed filter parameters (`severity`, `known_exploit`, `affecting`, `sort`, `operating_system`) without needing an OpenAPI schema lookup. Used proper JSON argument types (booleans as `true`, not `"true"`).
4. **pagination-handling** [PREFERRED]: Applied sensible defaults (limit=50 for hosts). For the "top 5" request, used `limit=5` with no follow-up offer. Would paginate host listings if total > 50.
5. **response-formatting** [GUIDANCE]: Structured output as summary + table. CVE table columns: CVE ID, CVSS Score, Severity, Affected RHEL 8 Systems, Remediation Available.
6. **guardrails-safety** [STRICT]: Emphasized known exploits per the rule "CVEs with known_exploit=true deserve extra emphasis regardless of severity label." Presented severity labels exactly as reported by the API.
7. **error-handling** [PREFERRED]: Not directly triggered here, but would be applied if any tool call returned an error (e.g., retry with narrower query on `tool_result_too_large`, interpret HTTP status codes).
