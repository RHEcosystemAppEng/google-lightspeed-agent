# Eval 6: "List my registered systems" — Tool Call Plan (old_skill v1.2)

## Analysis

This is a straightforward single-tool request. The user wants to see their registered systems, which maps directly to the Inventory service.

### Skill Guidance Applied

- **multi-step-workflows (v1.1)** — Tool disambiguation table: General "list my systems" maps to `inventory__list_hosts`, which is the source of truth for the full fleet (all registered systems including immutable/edge). The skill explicitly states: *"When a request genuinely maps to a single tool (e.g., 'list my hosts' -> `inventory__list_hosts`), a single call is fine."*
- **tool-invocation-rules (v1.2)** — Known parameters for `inventory__list_hosts`: `limit`, `offset`, `hostname_or_id`, `display_name`, `tags`, `operating_system`, `order_by`, `order_how` (ASC/DESC).
- **response-formatting (v1.1)** — Host/inventory lists should use a table with columns: Display Name, OS (e.g., RHEL 8.9), Last Check-in. Include total count in a summary line. Inline lists are capped at 20 items; if more exist, show the first 20 and add a summary line.
- **efficient-counting (v1.1)** — Not directly triggered (user asked to "list," not "how many"), but the total count from the response metadata (`total` field) will be used for the summary line.

## Step-by-Step Plan

### Step 1: Call `inventory__list_hosts` (single call)

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "limit": 20,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Reasoning:**
- `inventory__list_hosts` is the correct tool per the multi-step-workflows disambiguation table — it queries the Inventory service, which is the source of truth for all registered systems (including immutable/edge systems). `vulnerability__get_systems` would be wrong here because it only returns systems tracked for CVE analysis, excluding immutable systems.
- `limit=20` aligns with the response-formatting skill's inline list cap of 20 items.
- `order_by=display_name` and `order_how=ASC` provide alphabetical ordering for readability.
- No filters are applied since the user wants to see all registered systems without restriction.

### Step 2: Format and present the response

**From the response, extract:**
- The `total` metadata field to report the overall fleet size.
- For each host in the results: display name, operating system, and last check-in timestamp.

**Output format** (per response-formatting skill):

Present as a table:

| Display Name | OS | Last Check-in |
|---|---|---|
| host-001.example.com | RHEL 9.4 | 2026-07-09 |
| host-002.example.com | RHEL 8.9 | 2026-07-08 |
| ... | ... | ... |

**Summary line:** "Showing 20 of **N** registered systems. Ask me to continue or apply filters (e.g., by operating system) to narrow down."

### Step 3: Handle edge cases

- **If the result is empty** (total = 0): Report "You have no registered systems in your inventory" as a valid finding, not an error (per error-handling skill: empty results are findings, not failures).
- **If the response is `tool_result_too_large`**: Reduce limit (e.g., to 10) and retry per the error-handling skill's oversized response strategy.
- **If 20 or fewer total systems**: Show all of them without the "and N more" suffix.
- **If more than 20 total systems**: Show the first 20 with the pagination prompt per response-formatting's inline list cap rule.

## Summary

| Step | Tool Call | Arguments | Purpose |
|---|---|---|---|
| 1 | `inventory__list_hosts` | `{"limit": 20, "order_by": "display_name", "order_how": "ASC"}` | Retrieve registered systems from Inventory |
| 2 | *(no tool call)* | — | Format results as table with total count |

**Total tool calls: 1**

This is correctly identified as a single-tool workflow. No chaining or multi-step resolution is needed because the user is not asking about a specific system, filtering by vulnerability context, or requesting cross-service correlation.
