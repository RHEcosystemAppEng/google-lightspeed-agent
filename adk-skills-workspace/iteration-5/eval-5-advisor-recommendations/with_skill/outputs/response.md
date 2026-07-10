# Advisor Recommendations: Step-by-Step Tool Call Plan

## User Question

> "What are the top advisor recommendations for my environment?"

## Reasoning

The user wants the highest-priority advisor recommendations. This requires two steps:

1. **Get an overview of the recommendation landscape** so I can provide context (total counts, category breakdown).
2. **Fetch the top recommendations sorted by risk** so the user sees the most impactful items first.

The skills guide this approach:

- **tool-invocation-rules** tells me to use `advisor__get_active_rules` with `impacting="true"` (string-typed boolean, not JSON boolean), and to sort by `"-total_risk"` for highest-risk-first ordering.
- **multi-step-workflows** says that for an "overview of infrastructure health" style question I should combine `advisor__get_recommendations_stats` with other tools to build a synthesized report.
- **efficient-counting** says I can get the total count of impacting rules with a single `limit=1` call and read `meta.count`.
- **response-formatting** says advisor recommendations should be grouped by severity or category, include the rule description and number of affected systems, and be capped at 20 items with a "...and N more" line if the total exceeds 20.
- **error-handling** says if any call returns `tool_result_too_large`, I should reduce `limit` or add filters (e.g., filter to a specific category or risk level) before falling back to asking the user.

## Step-by-Step Plan

### Step 1: Get Recommendation Statistics (Overview)

**Purpose:** Obtain a high-level summary of the advisor landscape -- total recommendations, breakdown by category and risk level -- to frame the detailed results.

```
tool: advisor__get_recommendations_stats
args: {}
```

No arguments needed; this returns aggregate stats for the entire environment.

**Reasoning:** This gives me the total number of active recommendations and their distribution, which I will use to introduce the results ("You have X total recommendations across your environment. Here are the highest-risk ones..."). The multi-step-workflows skill lists this as the first call in the "infrastructure health overview" pattern.

---

### Step 2: Get Total Count of Impacting Rules

**Purpose:** Determine how many recommendations are actively impacting systems, so I can report the total and decide whether pagination is needed.

```
tool: advisor__get_active_rules
args: {"limit": 1, "impacting": "true", "sort": "-total_risk"}
```

**Reasoning:** Per the efficient-counting skill, I use `limit=1` to get just the count from `meta.count` without transferring unnecessary data. I pass `impacting="true"` as a **string** (not a JSON boolean) per the tool-invocation-rules skill's "String-typed booleans -- CRITICAL" section. The sort parameter is included so the metadata is consistent with the next call.

---

### Step 3: Fetch Top Impacting Recommendations

**Purpose:** Retrieve the actual top recommendations sorted by total risk, with enough detail to present to the user.

```
tool: advisor__get_active_rules
args: {"limit": 20, "impacting": "true", "sort": "-total_risk"}
```

**Reasoning:**
- `limit=20`: The response-formatting skill caps inline lists at 20 items. I fetch the top 20 highest-risk rules.
- `impacting="true"` (string): Only rules that currently affect systems in the user's environment. This is the most relevant filter -- rules that don't impact any systems are noise.
- `sort="-total_risk"`: Descending by total risk, so the most critical recommendations appear first. The tool-invocation-rules skill confirms this sort parameter.

**If this call returns `tool_result_too_large`:** Per the error-handling skill, I would retry with `limit=10` or add a filter such as `category` to narrow results.

---

### Step 4: Synthesize and Present Results

**Purpose:** Combine the statistics and the top rules into a coherent, actionable response.

**Format (per response-formatting skill):**
1. **Summary paragraph** -- "Your environment has N active advisor recommendations impacting your systems. Here are the top ones by risk..."
2. **Grouped by severity/category** -- Present the recommendations grouped by risk level (Critical / Important / Moderate / Low), each with:
   - Rule description (what the issue is)
   - Number of affected systems
   - Whether automatic remediation is available
   - Category (Security, Availability, Stability, Performance)
3. **"...and N more" line** -- If the total from Step 2 exceeds 20, append: "...and N more recommendations. Ask me to continue or filter by category to narrow down."
4. **Actionable next steps** -- Suggest follow-up actions: "Would you like me to focus on a specific category (e.g., Security), show only rules with automatic remediation, or dive into a specific recommendation?"

## Summary of Tool Calls

| Step | Tool | Key Arguments | Purpose |
|------|------|---------------|---------|
| 1 | `advisor__get_recommendations_stats` | *(none)* | Environment-wide recommendation overview |
| 2 | `advisor__get_active_rules` | `limit=1, impacting="true", sort="-total_risk"` | Get total count of impacting rules |
| 3 | `advisor__get_active_rules` | `limit=20, impacting="true", sort="-total_risk"` | Fetch top 20 highest-risk recommendations |
| 4 | *(no tool call -- synthesis)* | | Format and present results to user |

**Note:** Steps 1 and 2 are independent of each other and could be executed in parallel. Step 3 depends on Step 2 only if I need to adjust the limit based on the total count, but since I default to 20 (the response-formatting cap), it can also run in parallel with Steps 1-2. Step 4 requires all prior results.

## Key Skill Applications

- **tool-invocation-rules v1.5**: Used string-typed booleans (`impacting="true"` not `true`), correct parameter names (`sort`, `limit`), and the confirmed sort value `"-total_risk"`.
- **multi-step-workflows v1.2**: Combined `advisor__get_recommendations_stats` with `advisor__get_active_rules` for a complete picture, following the "infrastructure health overview" pattern.
- **efficient-counting v1.1**: Used `limit=1` in Step 2 to get the total count from `meta.count` without fetching full data.
- **error-handling v1.1**: Planned fallback strategy for `tool_result_too_large` (reduce limit, add category filter).
- **response-formatting v1.1**: Planned output grouped by severity/category, capped at 20 items, with affected system counts and a "...and N more" continuation prompt.
