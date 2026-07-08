---
name: pagination-handling
description: |
  Navigating paginated results from Vulnerability, Inventory, Advisor,
  and other Red Hat Insights APIs. Use this skill when a response
  contains pagination metadata (offset, limit, total), when results
  are truncated, or when the user asks for a full list that may span
  multiple pages. [PREFERRED]
metadata:
  author: red-hat
  version: "1.1"
---

## Default Behavior: Fetch First, Ask Later

When the user does not specify a quantity or limit, fetch the first page with a
sensible default (e.g., 20 for CVE lists, 50 for host listings). After receiving
the response, check the total count from the metadata. If significantly more data
exists, tell the user the total and offer to fetch more:

> "Showing 20 of 1,247 CVEs (sorted by severity). Would you like me to fetch more,
> or apply filters (e.g., Critical only, remediatable) to narrow the results?"

Do not present a pagination menu before the first call — answer the question first,
then let the user decide.

**When to skip the offer** (user already specified scope):
- "Show me the top 3 CVEs on host X" -> use limit=3, no follow-up needed
- "Get the first page of vulnerabilities" -> use limit=100 offset=0, no follow-up
- "How many critical CVEs affect host X?" -> use the efficient-counting approach
  (limit=1 + metadata)

**Exception — remediatable CVE queries**: When the user asks for remediatable CVEs on a
specific system, fetch all pages automatically. Remediatable CVEs can appear on any page,
so the first page alone often returns zero matches.

## Pagination Execution

For multi-page fetches, call the same MCP tool repeatedly, advancing `offset` each time.

### Vulnerability tools (JSON:API)

Paginated responses include `data`, `links`, and `meta`. Use `limit` (page size) and
`offset` (index of the first record). Advance offset by the limit you requested:
next `offset` = current `meta.offset` + `meta.limit`.

After each response, read:
- `meta.total_items` — total rows matching the query
- `meta.limit`, `meta.offset` — current pagination state
- `links.next` — URL for the next page, or `null` when no more pages

### Other tool categories (Advisor, Inventory, Image Builder, ...)

May use different parameter names or response shapes (`results` + `page`/`per_page`/`total`).
After each response, advance `offset`/`page` using the metadata fields present. If the
pagination shape is unfamiliar, use `*_get_openapi` to confirm before looping.

## Stop Conditions

Stop fetching (whichever applies first) — do not issue another tool call when:

1. `links.next` is `null`, or
2. The next `offset` would be >= `meta.total_items`, or
3. `data` has fewer elements than `limit` (last partial page) or is empty, or
4. The user asked for "N pages" and you have made N successful requests (unless
   you already stopped due to 1-3).

If the user asked for "N pages" but fewer exist, stop when 1-3 apply and report
that fewer pages were available. This avoids out-of-range errors.

## Large Result Sets

Never refuse a pagination or filtering request as "beyond capacity." When the result
set is large:
1. Apply filters first (severity, status, date range, etc.) to narrow results.
2. Paginate through remaining pages using the stop conditions above.
3. If a tool call returns `tool_result_too_large`, reduce the page size and retry
   (e.g., from 100 to 20). See the error-handling skill for the full retry strategy.
4. For pure counting queries, use the efficient-counting approach instead of
   fetching all pages.
