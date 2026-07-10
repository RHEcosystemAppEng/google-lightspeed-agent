# Eval 5 — "What are the top advisor recommendations for my environment?"

## Step-by-Step Tool Call Plan

### Step 1: Fetch Advisor Recommendation Statistics

**Tool:** `advisor__get_recommendations_stats`
**Arguments:** `{}`
**Reasoning:** Before diving into individual recommendations, I start by getting an overview of the advisor landscape — how many total recommendations exist, broken down by severity/category. This gives me context for what "top" means and helps me frame the results for the user. The multi-step-workflows skill lists this tool in the "infrastructure health" workflow example, confirming it exists and is the right entry point for advisor data.

### Step 2: Fetch the Top Active Advisor Rules

**Tool:** `advisor__get_active_rules`
**Arguments:** `{"limit": 20, "sort": "-total_risk"}`
**Reasoning:** This is the core call. I fetch the top 20 active advisor rules (recommendations), sorted by total risk descending so the most impactful recommendations appear first. The efficient-counting skill confirms `advisor__get_active_rules` is a known tool. I use `limit=20` as the response-formatting skill caps inline lists at 20 items. I use `-total_risk` as the sort parameter to surface the highest-risk recommendations first (the "top" ones). If the tool doesn't support `-total_risk` as a sort field, I would fall back to fetching without sort and manually prioritizing by risk in my response.

### Step 3: Check Pagination Metadata

**No additional tool call — metadata inspection from Step 2's response.**
**Reasoning:** Per the pagination-handling skill, after receiving the response I check `meta.count` (Advisor uses this field per the efficient-counting skill) to see how many total recommendations exist. If significantly more than 20 exist, I tell the user the total and offer to fetch more or apply filters. If 20 or fewer, I present all results directly.

### Step 4: Present Results Grouped by Severity/Category

**No additional tool call — formatting of Step 2's results.**
**Reasoning:** Per the response-formatting skill's "Advisor recommendations" section, I group the results by severity or category, include the rule description and number of affected systems for each recommendation. I lead with a brief summary paragraph (e.g., "You have X active advisor recommendations across your environment. Here are the top 20 by risk:"), then present the grouped data.

## Complete Execution Flow

```
User: "What are the top advisor recommendations for my environment?"

Step 1: advisor__get_recommendations_stats {}
  -> Get overall counts and severity breakdown
  -> Provides context: "Your environment has N total recommendations"

Step 2: advisor__get_active_rules {"limit": 20, "sort": "-total_risk"}
  -> Fetch top 20 rules sorted by risk
  -> Each rule includes: description, category, severity/risk, affected system count

Step 3: Inspect meta.count from Step 2 response
  -> If total > 20: note "Showing 20 of N recommendations"
  -> If total <= 20: present all

Step 4: Format response
  -> Summary paragraph with total counts from Step 1
  -> Table or grouped list from Step 2, organized by severity
  -> Offer to drill into specific recommendations or filter by category
```

## Example Response Format

Based on the response-formatting skill guidance, the final answer would look like:

> Your environment has **142 active advisor recommendations**. Here are the top 20 by risk:
>
> **Critical Risk (3)**
> | Rule | Category | Affected Systems |
> |---|---|---|
> | [description] | Security | 12 |
> | [description] | Performance | 8 |
> | [description] | Availability | 5 |
>
> **Important Risk (7)**
> | Rule | Category | Affected Systems |
> |---|---|---|
> | ... | ... | ... |
>
> ...and 122 more recommendations. Would you like me to filter by category (Security, Performance, Availability, Stability) or show the next page?

## Skill References Used

1. **tool-invocation-rules**: Confirmed that I should make actual tool calls with JSON arguments, not pseudocode. Verified argument formatting (native JSON types, omit unused optional args).
2. **multi-step-workflows**: The "infrastructure health" workflow example explicitly includes `advisor__get_recommendations_stats` as the first call, validating my approach. Also confirms chaining multiple tools for a complete picture.
3. **pagination-handling**: Guides the "fetch first, ask later" approach — get the first page with a sensible default (20), then check metadata and offer to continue. Advisor tools use `meta.count` for totals.
4. **efficient-counting**: Confirms the `meta.count` metadata field path for Advisor tools, which I use to read the total without fetching all pages.
5. **response-formatting**: Specifies that advisor recommendations should be "grouped by severity or category" with "rule description and number of affected systems" included.
6. **error-handling**: If any call returns `tool_result_too_large`, I reduce `limit` (e.g., to 10) and retry. If a 401/403 is returned, I inform the user about permissions. Empty results are reported as a finding ("No active recommendations — your environment looks healthy").
7. **guardrails-safety**: Notes the overlap between Advisor recommendations (configuration best practices) and Vulnerability data (known CVEs) — if both flag the same system, I note the overlap but don't dismiss either. Also ensures I present severity labels exactly as reported.
