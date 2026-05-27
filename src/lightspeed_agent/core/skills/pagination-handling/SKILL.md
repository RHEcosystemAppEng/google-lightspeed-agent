---
name: pagination-handling
description: |
  Teaches the agent how to handle paginated API responses correctly.
  Covers default fetch behavior, pagination metadata interpretation,
  stop conditions, and per-API pagination conventions for Vulnerability,
  Inventory, Advisor, and other tool categories. [PREFERRED]
metadata:
  author: red-hat
  version: "1.0"
---

## Pagination Awareness [PREFERRED]

Several tools return paginated results. Systems can have 1,000+ CVEs, accounts can have
thousands of hosts.

**Default behavior — fetch first, ask later**: When the user does NOT specify a quantity
or limit, fetch the first page with a sensible default (e.g., 20 for CVE lists, 50 for
host listings). After receiving the response, check `meta.total_items`. If significantly
more data exists, tell the user the total and offer to fetch more:

"Showing 20 of 1,247 CVEs (sorted by severity). Would you like me to fetch more,
or apply filters (e.g., Critical only, remediatable) to narrow the results?"

Do NOT present a pagination menu before the first call — answer the question first,
then let the user decide whether they need more.

**When to skip the offer** (user already specified scope):
- "Show me the top 3 CVEs on host X" → use limit=3, no follow-up needed
- "Get the first page of vulnerabilities" → use limit=100 offset=0, no follow-up needed
- "How many [resources]?" → use the efficient counting technique below

### Efficient Counting [PREFERRED]

When the user asks "how many [resources]?" (total count questions), do NOT fetch all
pages to count. Instead, call the relevant MCP tool with `limit=1` and `offset=0` and
read the total from the response metadata — one API call, no data transfer:

- **Vulnerability tools** (JSON:API responses): total is at `meta.total_items`
- **Inventory tools**: total is at `total`
- **Advisor, Content Sources, Image Builder, RHSM tools**: total is at `meta.count`

Pass the user's filters as normal tool arguments alongside `limit=1`.

**Examples:**
- "How many CVEs?" → call `vulnerability__get_cves` with `limit=1`, report `meta.total_items`
- "How many critical CVEs?" → call `vulnerability__get_cves` with `limit=1, severity=Critical`,
  report `meta.total_items`
- "How many hosts?" → call `inventory__list_hosts` with `limit=1`, report `total`
- "How many hosts running RHEL 9?" → call `inventory__list_hosts` with
  `limit=1, operating_system=RHEL 9`, report `total`
- "How many advisor rules?" → call `advisor__get_active_rules` with `limit=1`,
  report `meta.count`
- "How many blueprints?" → call `image-builder__get_blueprints` with `limit=1`,
  report `meta.count`

**Exception — remediatable CVE queries**: When the user asks for remediatable CVEs on a
specific system, fetch all pages automatically. Remediatable CVEs can appear on any page,
so the first page alone often returns zero matches.

**Pagination execution**: For multi-page fetches, **call the same MCP tool repeatedly**
with JSON arguments from the tool schema (see **Tool invocation format** above).
[Red Hat Lightspeed MCP](https://github.com/RedHatInsights/insights-mcp) returns Insights
API JSON as-is; list responses are often JSON:API-style (`data`, `meta`, `links`) or
`results` with `page`/`per_page`/`total` — read the fields present. If the pagination
shape is unclear, fall back to `*_get_openapi` to confirm.

**Vulnerability tools** (OpenAPI `application/vnd.api+json`): Paginated responses include
three required top-level keys: **`data`**, **`links`**, and **`meta`**. Use query
parameters **`limit`** (page size) and **`offset`** (index of the first record). The
API defines **`page`** / **`page_size`** too, but **limit/offset pagination takes
precedence** over page-based pagination — prefer **`limit`** and **`offset`** for every
call. Advance **`offset`** by **`meta.limit`** from the response (or by the `limit` you
requested), e.g. next `offset` = current `meta.offset` + `meta.limit`.

**Pagination metadata** (critical — avoids invalid requests and misleading errors such
as HTTP 403 on out-of-range pages): After **each** response, read:

- **`meta.total_items`**: total rows available for this query (integer).
- **`meta.limit`**, **`meta.offset`**, **`meta.page`**, **`meta.page_size`**, **`meta.pages`**:
current pagination state from the server.
- **`links.next`**: URL for the next page, or **`null`** when there is **no** next page.

**Stop fetching** (whichever applies first) — do **not** issue another tool call to load
"more pages" when:

1. **`links.next`** is **`null`**, or
2. The next **`offset`** you would use is **≥ `meta.total_items`**, or
3. **`data`** is a JSON array with **fewer elements than `limit`** (last partial page)
or **empty**, or
4. The user asked for "N pages" and you have already made **N** successful requests
— unless you already stopped earlier due to (1)–(3).

If the user asked for "N pages" but fewer pages exist, stop when (1)–(3) say so and
report that fewer pages were available (avoids empty-page / out-of-range errors).

**Other tool categories** (Advisor, Inventory, Image Builder, …) may use different
parameter names or response shapes. After each response, advance `offset`/`page`
using `meta`/`links.next` or `total`/`per_page` as appropriate for that API.
If the pagination shape is unfamiliar, use `*_get_openapi` to confirm before looping.
