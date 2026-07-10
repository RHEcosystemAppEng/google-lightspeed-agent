# Eval 5: "What are the top advisor recommendations for my environment?"

## Skill Version

tool-invocation-rules v1.2 (with companion skills: multi-step-workflows v1.1, efficient-counting v1.1, error-handling v1.1, response-formatting v1.1)

## Step-by-Step Plan

### Step 1: Retrieve Advisor Recommendation Statistics

**Tool call:**
```
tool: advisor__get_recommendations_stats
args: {}
```

**Reasoning:** The multi-step-workflows skill (under the "Give me an overview of my infrastructure health" workflow example) identifies `advisor__get_recommendations_stats` as the first tool to call for advisor-related queries. This gives a high-level summary of recommendation counts by severity/category, providing an overview of the environment's advisory posture before diving into details.

This call requires no arguments — it returns aggregate statistics for the user's environment.

---

### Step 2: Retrieve the Top Active Advisor Rules

**Tool call:**
```
tool: advisor__get_active_rules
args: {"limit": 20, "sort": "-total_risk"}
```

**Reasoning:** To answer "top advisor recommendations," I need to fetch the actual recommendation rules ranked by importance. The `advisor__get_active_rules` tool returns the active recommendation rules in the user's environment. I use:

- `limit=20`: The response-formatting skill caps inline lists at 20 items, so I fetch up to 20 to present the most important ones.
- `sort=-total_risk`: Sorting by descending total risk ensures the highest-impact recommendations appear first (the "-" prefix indicates descending order, following the same convention as the vulnerability tools documented in tool-invocation-rules).

**Note on tool discovery:** The tool-invocation-rules skill states that I should only invoke tools that are registered and available in my current toolset, and should not invent tool names. The `advisor__get_active_rules` tool is referenced in the efficient-counting skill as a known tool (used in the counting example for advisor rules with `meta.count`), confirming it exists. The `advisor__get_recommendations_stats` tool is referenced in multi-step-workflows, also confirming its availability.

**Note on argument formatting:** Per the tool-invocation-rules skill, I pass arguments as native JSON types — `20` as a number (not `"20"`), and the sort string as `"-total_risk"`. I omit optional arguments I don't need rather than passing `null`.

---

### Step 3: Present the Results

**Reasoning (no tool call — synthesis step):** Per the response-formatting skill:

- **Group by severity or category**: Advisor recommendations should be grouped by severity or category, with the rule description and number of affected systems included.
- **Lead with a summary**: Since Step 1 provided statistics, I would open with a brief summary paragraph (e.g., "Your environment has X active recommendations, including Y critical and Z important ones").
- **Tabular format**: Present the top recommendations in a structured format including:
  - Rule description
  - Severity / total risk
  - Category (performance, security, availability, stability)
  - Number of affected systems
- **Cap at 20 items**: If more than 20 active rules exist, show the top 20 and add: "...and N more. Ask me to continue or apply filters to narrow down."
- **Actionable guidance**: Per the response-formatting skill's directive to be "helpful, clear, and actionable," I would highlight which recommendations to prioritize and suggest next steps (e.g., "Would you like me to show the affected systems for any of these recommendations?").

---

## Error Handling Considerations

Per the error-handling skill:

- **If `advisor__get_recommendations_stats` returns `tool_result_too_large`**: This is unlikely for a stats endpoint, but if it happens, I would retry with any available filters.
- **If `advisor__get_active_rules` returns `tool_result_too_large`**: I would reduce the limit (e.g., from 20 to 10) or add filters (e.g., a specific category or severity level).
- **If either call returns a 401/403**: I would tell the user to re-authenticate or check their RBAC permissions.
- **If either call returns a 404**: I would report that the advisor service resource was not found.
- **If either call returns a 500/502/503**: I would retry once, then report the service is temporarily unavailable.
- **Empty results**: If no active rules are returned, I would report this as a positive finding: "No active advisor recommendations were found for your environment — your systems are following best practices."

## Summary

| Step | Tool | Arguments | Purpose |
|------|------|-----------|---------|
| 1 | `advisor__get_recommendations_stats` | (none) | Get high-level summary of recommendation counts |
| 2 | `advisor__get_active_rules` | `limit=20, sort=-total_risk` | Fetch top 20 recommendations ranked by risk |
| 3 | (synthesis) | — | Format results grouped by severity/category with affected system counts |

**Total tool calls: 2**

This is a relatively straightforward query that maps well to the advisor tools. The multi-step-workflows skill confirms this pattern in the "infrastructure health" workflow example. No cross-service chaining (e.g., to Inventory or Vulnerability) is needed unless the user asks follow-up questions about specific affected systems.
