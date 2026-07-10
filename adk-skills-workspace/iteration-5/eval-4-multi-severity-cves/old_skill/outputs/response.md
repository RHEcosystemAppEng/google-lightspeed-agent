# Eval 4: "Show me the top critical and important CVEs affecting my systems."

## Analysis

This query has three key requirements:

1. **Multiple severities** -- the user wants both Critical AND Important CVEs.
2. **Affecting my systems** -- only CVEs that affect at least one system in the user's inventory.
3. **Top** -- the most severe/highest-scoring CVEs first.

The critical constraint from the `tool-invocation-rules` skill (v1.2) is that the `severity` parameter on `vulnerability__get_cves` accepts **exactly one value** -- never a list or comma-separated string. For multi-severity queries, the skill prescribes two strategies:

1. **Preferred -- sort by score**: Omit `severity` entirely and use `sort=-cvss_score`. The top results will naturally be Critical and Important.
2. **Separate calls**: Make one call per severity and merge results.

The `multi-step-workflows` skill (v1.1) reinforces this: its workflow example for "What are the most critical vulnerabilities on my systems?" uses `vulnerability__get_cves` with `sort=-cvss_score, affecting=true, limit=20` -- no `severity` filter.

## Step-by-Step Plan

### Strategy A: Preferred Approach (Single Call, Sort by CVSS Score)

#### Step 1: Fetch top CVEs sorted by CVSS score, filtered to those affecting the user's systems

```
tool: vulnerability__get_cves
args: {"limit": 20, "sort": "-cvss_score", "affecting": true}
```

**Reasoning:**
- `sort=-cvss_score` orders results by CVSS score descending, so Critical (CVSS 9.0-10.0) and Important (CVSS 7.0-8.9) CVEs appear first naturally.
- `affecting=true` restricts results to only CVEs that affect at least one of the user's registered systems, directly answering "affecting my systems."
- `limit=20` retrieves a manageable top-20 list, following the response-formatting skill's guidance to cap inline lists at 20 items.
- `severity` is deliberately omitted because it only accepts a single value, and we want both Critical and Important.

#### Step 2: Present results

**Reasoning:** Per the `response-formatting` skill, CVE lists should be presented as a table with columns: CVE ID, Severity, Affected Systems, Remediation Available. Results are sorted by severity descending (which the CVSS sort already achieves). If the total count (from `meta.total_items`) exceeds 20, add a summary line noting how many more exist.

**Note:** The results may include some Moderate-severity CVEs at the tail of the 20 if there are fewer than 20 Critical+Important CVEs. This is acceptable -- the user sees the most severe CVEs first, and any Moderate entries provide additional context. If the user wants strictly only Critical and Important, the separate-calls approach (Strategy B) can be used instead.

---

### Strategy B: Separate Calls (Strict Severity Filtering)

If the user strictly wants only Critical and Important CVEs (no Moderate or Low), use two separate calls:

#### Step 1: Fetch top Critical CVEs affecting the user's systems

```
tool: vulnerability__get_cves
args: {"limit": 10, "severity": "Critical", "sort": "-cvss_score", "affecting": true}
```

**Reasoning:**
- `severity="Critical"` filters to only Critical-severity CVEs (single value, as required by the tool).
- `affecting=true` restricts to CVEs impacting the user's systems.
- `sort=-cvss_score` orders by highest CVSS score first within the Critical tier.
- `limit=10` retrieves the top 10 Critical CVEs.

#### Step 2: Fetch top Important CVEs affecting the user's systems

```
tool: vulnerability__get_cves
args: {"limit": 10, "severity": "Important", "sort": "-cvss_score", "affecting": true}
```

**Reasoning:**
- Same approach as Step 1 but with `severity="Important"`.
- `limit=10` retrieves the top 10 Important CVEs.

#### Step 3: Merge and present results

**Reasoning:** Combine the results from both calls into a single table sorted by severity (Critical first, then Important), then by CVSS score within each severity tier. Per the `response-formatting` skill, present as a table with CVE ID, Severity, Affected Systems, Remediation Available columns.

---

## Why Strategy A Is Preferred

The `tool-invocation-rules` skill explicitly marks the sort-by-score approach as **"Preferred"** for multi-severity queries. The `multi-step-workflows` skill's example workflow also uses this pattern. The advantages:

1. **Fewer API calls** -- one call instead of two, reducing latency and rate-limit risk.
2. **Simpler logic** -- no need to merge results from separate calls.
3. **Natural ranking** -- CVSS score provides a unified ordering across severity tiers, showing the user truly the "top" CVEs regardless of which severity bucket they fall in.

Strategy B is appropriate when the user explicitly needs strict severity filtering with no Moderate/Low CVEs in the results, or when they want a specific number from each severity tier.

## Error Handling Considerations

Per the `error-handling` skill:
- If the call returns `tool_result_too_large`, retry with a smaller `limit` (e.g., `limit=10`) or add `severity="Critical"` to narrow the result set.
- If a 401/403 is returned, inform the user to re-authenticate.
- If a 429 (rate-limited) is returned, retry once; if it fails again with Strategy B, note that two calls increase rate-limit exposure.
- An empty result set is valid and good news -- report "No critical or important CVEs are currently affecting your systems."
