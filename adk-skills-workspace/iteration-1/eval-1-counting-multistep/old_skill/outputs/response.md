# Eval 1 — Counting + Multi-Step: Old Skills Response

## User Query

> "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Skill Analysis

This query has **two parts**:

1. **"How many critical CVEs with known exploits are affecting my RHEL 8 systems?"** — This is a **counting query** that also requires a **multi-step workflow** (must identify RHEL 8 systems first, then query CVEs with filters).
2. **"Can you show me the top 5 most severe ones with details?"** — This requires **fetching actual data** (not just a count) with a limit and sorting.

### Skills Activated

| Skill | Reason |
|---|---|
| `efficient-counting` | Part 1 is a "how many" question — use `limit=1` to get the total from metadata |
| `multi-step-workflows` | The query spans Inventory (RHEL 8 systems) and Vulnerability (CVEs) — requires chaining tool calls |
| `tool-invocation-rules` | Must invoke tools correctly with JSON arguments via function-calling |
| `pagination-handling` | Part 2 fetches actual data (top 5), so pagination awareness applies |
| `response-formatting` | CVE lists should use table format with severity, affected systems, remediation columns |
| `guardrails-safety` | CVEs with `known_exploit=true` deserve extra emphasis per the severity rules |

---

## Step-by-Step Plan

### Step 1: Find RHEL 8 systems in inventory

**Reasoning:** The user asks about "my RHEL 8 systems," so I need to identify which systems run RHEL 8. Per `multi-step-workflows`, the pattern for "What critical CVEs affect my RHEL 8 systems?" is: first find RHEL 8 systems (Inventory), then get CVEs for those systems (Vulnerability). I use `inventory__list_hosts` (not `vulnerability__get_systems`) because this is a general fleet query scoped by OS — per the tool disambiguation table, `inventory__list_hosts` is the source of truth for the full fleet.

**Tool call:**
```
tool: inventory__list_hosts
args: {"operating_system": "RHEL 8", "limit": 50}
```

**Expected result:** A list of hosts with their IDs, display names, OS versions, and a `total` field giving the full count of RHEL 8 systems. I'll note the total for the user and collect host IDs for subsequent steps.

If more than 50 RHEL 8 systems exist, I would note the total but proceed with the vulnerability query — the next steps use organization-wide CVE queries with filters rather than per-host queries, so I don't need every host ID upfront.

---

### Step 2: Get the count of critical CVEs with known exploits (efficient counting)

**Reasoning:** Part 1 is a "how many" question. Per the `efficient-counting` skill, I should NOT fetch all pages to count. Instead, I call the vulnerability tool with `limit=1` and read `meta.total_items`. The user wants critical severity + known exploits + affecting their systems, so I apply all three filters.

Per `multi-step-workflows`, `vulnerability__get_cves` supports: `severity`, `known_exploit`, `affecting`, `limit`, `offset`, `sort`. I use `affecting=true` to scope to CVEs that actually affect at least one of the user's systems (organization-scoped via JWT). This avoids needing to query per-host.

**Tool call:**
```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 1, "offset": 0}
```

**Expected result:** The response will contain `meta.total_items` with the count of critical CVEs with known exploits affecting the user's systems. The `data` array will have at most 1 item (which I won't use for display — just the count).

**Note:** This gives critical CVEs with known exploits across ALL the user's systems, not just RHEL 8. The `vulnerability__get_cves` tool filters at the organization level and does not accept an `operating_system` parameter directly. To get RHEL-8-only CVEs, I would need to query per system using `vulnerability__get_system_cves`. However, since the user's fleet may be mostly RHEL 8, I'll first provide the org-wide count and then clarify whether it needs to be RHEL-8-specific by cross-referencing. See Step 2b below.

---

### Step 2b (Conditional): Refine count to RHEL 8 systems only

**Reasoning:** If the user has systems running other RHEL versions (not just RHEL 8), the org-wide count from Step 2 might overcount. To get an accurate RHEL-8-only count, I would need to query CVEs per RHEL 8 host. However, this could be expensive if there are many RHEL 8 hosts.

**Approach:** If Step 1 shows the user has systems on multiple RHEL versions, I would:
- Pick the RHEL 8 host IDs from Step 1
- For each RHEL 8 host (or a representative sample), call `vulnerability__get_system_cves` with the appropriate filters
- Use the `efficient-counting` approach (`limit=1`) to get per-host counts

**Tool call (per RHEL 8 host):**
```
tool: vulnerability__get_system_cves
args: {"inventory_id": "<host_id_from_step_1>", "severity": "Critical", "known_exploit": true, "limit": 1}
```

**However:** If ALL the user's systems are RHEL 8 (Step 1 total matches the org fleet total), then the org-wide count from Step 2 is already RHEL-8-specific and no refinement is needed.

**Pragmatic decision:** I would report the org-wide count from Step 2 with a note like "across your RHEL 8 fleet" if RHEL 8 is the only OS, or clarify the scope if mixed.

---

### Step 3: Fetch the top 5 most severe CVEs with details

**Reasoning:** Part 2 asks for actual data — the top 5 most severe ones with details. Per `pagination-handling`, when the user specifies a quantity ("top 5"), I use `limit=5` and no follow-up pagination is needed. Per `response-formatting`, CVE lists should be formatted as tables. Per `guardrails-safety`, CVEs with `known_exploit=true` deserve extra emphasis.

I sort by `-cvss_score` (descending CVSS score) to get the most severe first, and keep the same filters from Step 2.

**Tool call:**
```
tool: vulnerability__get_cves
args: {"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 5, "offset": 0, "sort": "-cvss_score"}
```

**Expected result:** Up to 5 CVE records in `data`, each containing CVE ID, CVSS score, severity, description, known exploit status, affected system count, remediation availability, and other details.

---

### Step 4: Enrich with affected system details (optional, per multi-step-workflows)

**Reasoning:** Per `multi-step-workflows`, the example "What are the most critical vulnerabilities on my systems?" suggests cross-referencing with `vulnerability__get_cve_systems` and `inventory__get_host_details` for system context. Since the user asked for "details," I would enrich the top 5 CVEs with their affected RHEL 8 system names.

**Tool calls (for each of the top 5 CVEs):**
```
tool: vulnerability__get_cve_systems
args: {"cve_id": "<cve_id_from_step_3>", "limit": 5}
```

This gives me the specific systems affected by each CVE. I can then cross-reference with the RHEL 8 host list from Step 1 to show which RHEL 8 systems are impacted.

---

## Expected Response Format

Per `response-formatting` and `guardrails-safety`:

1. **Lead with the count** (from Step 2): "There are **X critical CVEs with known exploits** currently affecting your RHEL 8 systems."

2. **Emphasize known exploits** (per `guardrails-safety`): "All of these have known exploits in the wild, which means they should be prioritized for remediation regardless of other factors."

3. **Present the top 5 in a table** (per `response-formatting` CVE list format):

| CVE ID | CVSS Score | Severity | Affected Systems | Remediation Available | Description |
|--------|-----------|----------|------------------|-----------------------|-------------|
| CVE-2024-XXXX | 9.8 | Critical | 12 systems | Yes | ... |
| CVE-2024-YYYY | 9.6 | Critical | 8 systems | Yes | ... |
| ... | ... | ... | ... | ... | ... |

4. **Actionable recommendation**: Suggest prioritizing remediation for the CVEs with the highest CVSS scores and most affected systems, noting that modifications must be done through the user's normal change management process (per `guardrails-safety` read-only mode rule).

---

## Summary of Tool Calls

| Step | Tool | Arguments | Purpose |
|------|------|-----------|---------|
| 1 | `inventory__list_hosts` | `{"operating_system": "RHEL 8", "limit": 50}` | Identify RHEL 8 systems |
| 2 | `vulnerability__get_cves` | `{"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 1, "offset": 0}` | Efficient count of matching CVEs |
| 3 | `vulnerability__get_cves` | `{"severity": "Critical", "known_exploit": true, "affecting": true, "limit": 5, "offset": 0, "sort": "-cvss_score"}` | Fetch top 5 CVEs with details |
| 4 | `vulnerability__get_cve_systems` | `{"cve_id": "<each_cve_id>", "limit": 5}` (x5) | Affected system details per CVE |

**Total tool calls:** 3 mandatory + up to 5 optional enrichment = 3–8 calls.

---

## Skill Compliance Checklist

- [x] **efficient-counting**: Used `limit=1` + `meta.total_items` for the "how many" part (Step 2)
- [x] **multi-step-workflows**: Chained Inventory -> Vulnerability calls; used documented filter parameters (`severity`, `known_exploit`, `affecting`, `sort`)
- [x] **tool-invocation-rules**: All tool calls use JSON arguments via function-calling; no Python/pseudocode
- [x] **pagination-handling**: User specified "top 5" so `limit=5` used, no unnecessary pagination
- [x] **response-formatting**: CVE table format with required columns; sort by severity descending
- [x] **guardrails-safety**: Extra emphasis on known exploits; read-only mode noted for remediation; severity labels presented as-is from the API
- [x] **error-handling**: Ready to handle `tool_result_too_large` by reducing limit or adding filters; will distinguish empty results from errors
