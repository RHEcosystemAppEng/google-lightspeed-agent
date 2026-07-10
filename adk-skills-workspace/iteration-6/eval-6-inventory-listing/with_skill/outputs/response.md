# Eval 6 — "List my registered systems" (with skills)

## User Request

> "List my registered systems."

## Skill Analysis

Before making any tool call, I load the relevant skills and reason about the request:

1. **tool-invocation-rules** (STRICT) — Must be loaded before any MCP tool call. It contains the exact parameter names, types, and recommended defaults. For "List my systems" it provides a ready-made argument set.

2. **multi-step-workflows** — Contains tool disambiguation rules. Two tools list systems: `inventory__list_hosts` (all registered systems) and `vulnerability__get_systems` (only CVE-tracked systems). The disambiguation rule is explicit: *"General 'list my systems' -> `inventory__list_hosts` (source of truth for the full fleet)."* This is a general listing request with no vulnerability context, so `inventory__list_hosts` is the correct tool.

3. **pagination-handling** — States: *"When the user does not specify a quantity or limit, fetch the first page with a sensible default (e.g., 50 for host listings)."* After receiving results, check the total count and offer to fetch more if significantly more data exists. The tool-invocation-rules skill recommends `per_page=10` on first call.

4. **response-formatting** — For host/inventory lists, use a table with columns: **Display Name**, **OS** (e.g., RHEL 8.9), **Last Check-in**. Sort by display name ascending. Include total count in a summary line.

5. **efficient-counting** — Not the primary skill here since the user wants a listing (not just a count), but the total count from the response metadata will be used in the summary line.

6. **error-handling** — If the tool call returns `tool_result_too_large`, reduce `per_page` and retry. If it returns an HTTP error, follow the error code handling table.

7. **guardrails-safety** — No edge cases triggered. This is a straightforward, in-scope inventory query.

## Step-by-Step Plan

### Step 1: Call `inventory__list_hosts` with recommended defaults

**Reasoning:** The multi-step-workflows skill explicitly maps "list my systems" to `inventory__list_hosts`. The tool-invocation-rules skill provides the exact recommended argument set for this query pattern. I use `per_page=10` on the first call (as specified), sorted by display name ascending for a clean user-facing listing.

```
tool: inventory__list_hosts
args: {
  "per_page": 10,
  "page": 1,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Why these arguments:**
- `per_page: 10` — The tool-invocation-rules skill mandates: *"use 10 on first call"*
- `page: 1` — Start at the beginning (pages are 1-indexed per the schema)
- `order_by: "display_name"` — The tool-invocation-rules skill says: *"always include `display_name` for user-facing listings"*; the response-formatting skill also requires sorting by display name ascending
- `order_how: "ASC"` — The tool-invocation-rules skill says: *"default to `ASC`"*
- No filters applied — the user wants all registered systems, not a filtered subset

### Step 2: Process the response and format output

**Reasoning:** The response-formatting skill specifies the exact output format for host/inventory lists.

From the API response, I extract:
- `total` field from response metadata (per efficient-counting skill: the Inventory API uses `total` as its count field)
- For each host in the results: display name, OS version, and last check-in timestamp

I then format the results as a table following the response-formatting skill:

| Display Name | OS | Last Check-in |
|---|---|---|
| host-a.example.com | RHEL 9.4 | 2026-07-10 |
| host-b.example.com | RHEL 8.9 | 2026-07-09 |
| ... | ... | ... |

And include a summary line with the total count.

### Step 3 (conditional): Offer pagination if more results exist

**Reasoning:** The pagination-handling skill says: *"After receiving the response, check the total count from the metadata. If significantly more data exists, tell the user the total and offer to fetch more."*

- If `total <= 10`: All systems are displayed. No pagination needed. Present the complete table.
- If `total > 10`: Present the first 10 systems in a table, then add a summary like: *"Showing 10 of 247 registered systems (sorted by name). Would you like me to show the next page or filter by a specific criteria?"*

If the user requests more, I would call `inventory__list_hosts` again with `page: 2` (and the same `per_page`, `order_by`, `order_how` arguments), repeating until the stop conditions from the pagination-handling skill are met.

### Step 4 (conditional): Handle errors

**Reasoning:** The error-handling skill provides recovery strategies.

- If `tool_result_too_large`: Retry with `per_page: 5` (reduce page size)
- If HTTP 401/403: Tell the user to re-authenticate or check RBAC permissions
- If HTTP 500/502/503: Retry once, then report the service is temporarily unavailable
- If timeout: Retry once, then report the service is not responding

## Why NOT Other Tools

- **`vulnerability__get_systems`** — Rejected. The multi-step-workflows skill is explicit: this tool only returns systems tracked for CVE analysis (excludes immutable/edge systems). For a general "list my systems" request, `inventory__list_hosts` is the source of truth for the full fleet.
- **`inventory__get_host_system_profile`** — Not needed for a simple listing. This tool is for detailed system profile data (RHEL version, packages) and should only be called for follow-up detail queries.
- **No multi-step workflow needed** — The multi-step-workflows skill itself acknowledges: *"When a request genuinely maps to a single tool (e.g., 'list my hosts' -> `inventory__list_hosts`), a single call is fine."*

## Summary

This is a single-tool query. One call to `inventory__list_hosts` with the recommended defaults from tool-invocation-rules provides the answer. The response is formatted as a table per response-formatting, with pagination offered if the total exceeds the first page. The key skill-driven decisions are:

1. **Tool selection**: `inventory__list_hosts` over `vulnerability__get_systems` (multi-step-workflows disambiguation rule)
2. **Arguments**: Exact recommended defaults from tool-invocation-rules (`per_page=10, page=1, order_by="display_name", order_how="ASC"`)
3. **Output format**: Table with Display Name, OS, Last Check-in columns (response-formatting)
4. **Pagination**: Fetch first, offer more if total exceeds page size (pagination-handling)
