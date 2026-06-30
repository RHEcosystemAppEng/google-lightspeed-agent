---
name: efficient-counting
description: |
  Answering "how many" and total-count questions for CVEs, hosts, advisory
  rules, blueprints, subscriptions, or content sources. Use this skill
  when the user asks for a count, total, or number of any resource —
  provides the efficient single-call approach instead of fetching all
  pages. [PREFERRED]
metadata:
  author: red-hat
  version: "1.1"
---

## Efficient Counting

When the user asks "how many [resources]?" (total count questions), do NOT fetch all
pages to count. Instead, call the relevant MCP tool with `limit=1` and `offset=0` and
read the total from the response metadata — one API call, no data transfer.

### Metadata field paths

| API family | Total field | Tools |
|---|---|---|
| Vulnerability | `meta.total_items` | `vulnerability__get_cves`, `vulnerability__get_system_cves`, `vulnerability__get_systems` |
| Inventory | `total` | `inventory__list_hosts` |
| Advisor / Content Sources / Image Builder / RHSM | `meta.count` | `advisor__get_active_rules`, `image-builder__get_blueprints`, etc. |

Pass the user's filters as normal tool arguments alongside `limit=1`.

### Examples

- "How many CVEs?" -> `vulnerability__get_cves` with `limit=1` -> report `meta.total_items`
- "How many critical CVEs?" -> `vulnerability__get_cves` with `limit=1, severity=Critical` -> report `meta.total_items`
- "How many hosts?" -> `inventory__list_hosts` with `limit=1` -> report `total`
- "How many hosts running RHEL 9?" -> `inventory__list_hosts` with `limit=1, operating_system=RHEL 9` -> report `total`
- "How many advisor rules?" -> `advisor__get_active_rules` with `limit=1` -> report `meta.count`
- "How many blueprints?" -> `image-builder__get_blueprints` with `limit=1` -> report `meta.count`

### Multi-step counting

Some counting queries require chaining tools — resolve identifiers first, then count:

**"How many critical remediable CVEs are on host X?"**
-> `inventory__list_hosts` (hostname_or_id=X) -> get the host ID ->
`vulnerability__get_system_cves` (severity=Critical, remediation=Applicable, limit=1) ->
read `meta.total_items` -> report the count.

**"How many systems are in my inventory?"**
-> `inventory__list_hosts` (limit=1) -> read `total` -> report the count.
Do NOT use `vulnerability__get_systems` for general system counts — that endpoint
returns only systems tracked for CVE analysis, excluding immutable systems.

### Important: counting never requires pagination

A "how many" question is always answerable with a single call per tool (using `limit=1`
plus the metadata). Never fetch all pages just to count, and never refuse a counting
request as "beyond capacity" — the metadata is designed for this.
