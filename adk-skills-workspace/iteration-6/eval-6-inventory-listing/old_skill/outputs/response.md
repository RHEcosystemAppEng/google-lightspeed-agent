# Eval 6 — "List my registered systems" (Old Skills)

## User Query

"List my registered systems."

## Analysis

This is a straightforward inventory listing request. According to the **multi-step-workflows** skill, the tool disambiguation table specifies:

> General "how many systems/hosts?" or "list my systems" -> `inventory__list_hosts` (source of truth for the full fleet).

This request maps to a single tool call — no multi-step chaining is needed. The user is asking to **list** (not count) systems, so I should fetch actual data rather than using the efficient-counting `limit=1` approach.

Per the **pagination-handling** skill, when the user does not specify a quantity or limit, I should "fetch the first page with a sensible default (e.g., 50 for host listings)." After receiving the response, I check the total and offer to fetch more if significantly more data exists.

## Step-by-Step Plan

### Step 1: Fetch the first page of registered systems

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "limit": 50,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Reasoning:**
- The **multi-step-workflows** skill explicitly identifies `inventory__list_hosts` as the correct tool for "list my systems" requests — it is the source of truth for the full fleet, including immutable/edge systems.
- I do NOT use `vulnerability__get_systems` because that only returns systems tracked for CVE analysis (excludes immutable systems), per the tool disambiguation table.
- I use `limit=50` as the sensible default for host listings per the **pagination-handling** skill.
- I sort by `display_name` ascending for a clean, alphabetical presentation per the **tool-invocation-rules** skill's known filter parameters (`order_by`, `order_how` are confirmed parameters for `inventory__list_hosts`).
- Per the **tool-invocation-rules** skill, I pass arguments as native JSON types (numbers as numbers, strings as strings) and omit optional arguments I don't need.

### Step 2: Present results and handle pagination

After receiving the response, I would:

1. **Read the pagination metadata** — specifically the `total` field (per the **efficient-counting** skill, Inventory uses `total` as its count field).

2. **Format the response** as a table per the **response-formatting** skill's "Host / inventory lists" section:
   - Columns: **Display Name**, **OS** (e.g., RHEL 8.9), **Last Check-in**
   - Include a total count in a summary line

3. **Handle pagination** per the **pagination-handling** skill:
   - If `total` <= 50: all systems are shown, no follow-up needed.
   - If `total` > 50: present the first 50 results and offer to fetch more: *"Showing 50 of [total] registered systems. Would you like me to fetch more, or apply filters (e.g., by operating system) to narrow the results?"*

4. **Check for stale data** per the **guardrails-safety** skill: if any system's `last_seen`/`updated` timestamp is older than 24 hours, note this in the response so the user knows the information may be outdated.

### Step 3 (conditional): Fetch additional pages if requested

If the user asks for more systems, I would make subsequent calls:

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "limit": 50,
  "offset": 50,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

And continue advancing `offset` by 50 each time, applying the **pagination-handling** stop conditions:
1. The next `offset` would be >= `total`, or
2. `data` has fewer elements than `limit` (last partial page) or is empty.

## Error Handling

Per the **error-handling** skill:

- If `inventory__list_hosts` returns `tool_result_too_large`: retry with a smaller `limit` (e.g., `limit=20`).
- If a 401/403 is returned: inform the user they may need to re-authenticate or check their RBAC permissions.
- If a 500/502/503 is returned: retry once, then report the service is temporarily unavailable.
- If the result is empty (zero hosts): report this as a valid finding — "No registered systems were found in your inventory" — not as an error.

## Example Output Format

Based on the **response-formatting** skill, the final response would look like:

> You have **[total]** registered systems. Here are your systems:
>
> | Display Name | OS | Last Check-in |
> |---|---|---|
> | pool0-infra001.example.com | RHEL 9.3 | 2 hours ago |
> | pool0-infra002.example.com | RHEL 8.9 | 1 hour ago |
> | webserver-prod-01.example.com | RHEL 9.2 | 30 minutes ago |
> | ... | ... | ... |
>
> Showing [N] of [total] registered systems. Would you like me to fetch more, or filter by operating system?

## Summary

| Step | Tool | Purpose |
|---|---|---|
| 1 | `inventory__list_hosts` | Fetch the first page of all registered systems (limit=50, sorted by display name) |
| 2 | *(no tool — formatting)* | Present results as a table, report total count, offer pagination if more exist |
| 3 (conditional) | `inventory__list_hosts` | Fetch subsequent pages if the user requests more |

**Key decisions:**
- Used `inventory__list_hosts` (not `vulnerability__get_systems`) because the user asked for "registered systems" — Inventory is the source of truth for the full fleet.
- Used `limit=50` (not `limit=1`) because the user wants to see the list, not just a count.
- Sorted by `display_name` for clean presentation.
- Will offer pagination follow-up only after showing initial results, per the "fetch first, ask later" principle.
