# Eval 5: "What are the top advisor recommendations for my environment?"

## Step-by-Step Tool Call Plan

### Step 1: Fetch Top Advisor Recommendations (Primary Query)

**Tool:** `advisor__get_active_rules`
**Arguments:**
```json
{
  "impacting": "true",
  "sort": "-total_risk",
  "limit": 20
}
```

**Reasoning:** This is the primary call to answer the user's question. Following the tool-invocation-rules skill, I use the recommended default for "Top advisor recommendations" queries exactly as specified. Key details:

- `impacting`: Set to `"true"` (as a **string**, not a JSON boolean — the MCP server rejects JSON booleans for this parameter, per the "String-typed booleans — CRITICAL" section of tool-invocation-rules).
- `sort`: Set to `"-total_risk"` to surface the highest-risk recommendations first. The minus prefix indicates descending order, so Critical and Important recommendations appear at the top.
- `limit`: Set to `20` to get a meaningful set of top recommendations without risking an oversized response. Per the pagination-handling skill, this is a sensible default — I will check the response metadata to see if significantly more exist.

### Step 2: Fetch Advisor Statistics (Complementary Context)

**Tool:** `advisor__get_recommendations_stats`
**Arguments:**
```json
{}
```

**Reasoning:** This call provides aggregate summary statistics for the user's advisor recommendations — total counts broken down by severity/category. Following the multi-step-workflows skill, combining multiple data sources builds a more complete answer. The stats give context to the specific rules from Step 1 (e.g., "You have 45 total recommendations; here are the top 20 by risk"). This matches the workflow example for "Give me an overview of my infrastructure health" which uses `advisor__get_recommendations_stats` as part of a multi-tool approach.

### Step 3: Process Results and Present Response

After receiving the results from both calls, I would:

1. **Check pagination metadata** from Step 1: Read `meta.count` to determine the total number of impacting rules. If significantly more than 20 exist, I will note the total and offer to fetch more or apply filters (per pagination-handling skill: "Showing 20 of N recommendations. Would you like me to continue or filter by category?").

2. **Handle errors if any**: Per the error-handling skill:
   - If `tool_result_too_large` is returned, retry with a smaller `limit` (e.g., `limit=10`) or add filters like `category` or `impact` to narrow results.
   - If a 401/403 error occurs, inform the user about potential permission issues.
   - If a 500/502/503 error occurs, retry once before reporting the service as unavailable.

3. **Format the response**: Per the response-formatting skill:
   - Group advisor recommendations by severity or category.
   - Include the rule description and number of affected systems for each recommendation.
   - Lead with a brief summary paragraph incorporating the stats from Step 2 (e.g., total recommendations, breakdown by risk level).
   - Cap at 20 items in the inline list; if more exist, include a summary line offering to continue or filter.

4. **Apply guardrails**: Per the guardrails-safety skill:
   - Note the distinction between Advisor recommendations (configuration best practices) and Vulnerability data (known CVEs) if there is overlap.
   - Emphasize urgency for Critical/Important recommendations affecting production systems.
   - If the data includes stale check-in timestamps (older than 24 hours), note that findings may not reflect the current state.
   - Frame empty results as a positive finding ("No high-risk advisor recommendations found — your environment follows best practices").

### Example Synthesized Response

After completing both tool calls, a response would look like:

---

Your environment has **[N] active advisor recommendations** impacting your systems. Here are the top 20, sorted by total risk:

| # | Rule Description | Total Risk | Category | Affected Systems | Remediation |
|---|---|---|---|---|---|
| 1 | [Rule description from API] | Critical | Security | 12 systems | Available |
| 2 | [Rule description from API] | Important | Performance | 8 systems | Available |
| ... | ... | ... | ... | ... | ... |

**Summary from advisor statistics:**
- Critical: X recommendations
- Important: Y recommendations
- Moderate: Z recommendations

Showing 20 of [total] recommendations. Would you like me to narrow these by category (e.g., Security, Performance, Availability) or show the next page?

---

## Why This Approach

1. **Two-call strategy** (not one): A single `advisor__get_active_rules` call answers the literal question, but adding `advisor__get_recommendations_stats` provides the contextual framing that makes the answer actionable. The multi-step-workflows skill explicitly encourages completing the full workflow rather than defaulting to one-and-done.

2. **No unnecessary calls**: The user asked specifically about advisor recommendations, so I do not call vulnerability or inventory tools — those would be appropriate for broader health overview questions but are not needed here. Per the multi-step-workflows skill: "When a request genuinely maps to a single tool, a single call is fine."

3. **String-typed booleans**: The `impacting` parameter is passed as `"true"` (string), not `true` (JSON boolean). This is critical — the MCP server rejects JSON booleans for this parameter, and getting this wrong would cause the tool call to fail silently or with an error.

4. **Recommended defaults applied**: The exact argument set `{"impacting": "true", "sort": "-total_risk", "limit": 20}` comes directly from the tool-invocation-rules skill's "Recommended defaults for common queries" section for advisor queries.

5. **Pagination awareness**: By checking `meta.count` after the first call, I can transparently report how much data exists and let the user decide whether to see more — following the pagination-handling skill's "fetch first, ask later" principle.
