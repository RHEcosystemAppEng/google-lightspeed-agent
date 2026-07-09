---
name: tool-invocation-rules
description: |
  Correct syntax, argument formatting, and known parameters for calling
  Red Hat Insights MCP tools. Use this skill when invoking a tool for the
  first time, when unsure about argument format or required parameters,
  or when a tool call was rejected due to malformed input. Includes the
  confirmed filter parameters for Vulnerability and Inventory tools. [STRICT]
metadata:
  author: red-hat
  version: "1.3"
---

## Invocation Format

Capabilities are exposed as MCP tools. Each action is a separate function call
with JSON arguments. Do not output Python, shell scripts, or pseudocode instead
of making an actual tool call — even when describing a multi-step plan.

**Correct:**
```
tool: vulnerability__get_cves
args: {"limit": 20, "impact": "7", "sort": "-cvss_score"}
```

**Wrong** (generating code instead of calling the tool):
```python
response = default_api.get_cves(limit=20, severity="Critical")
```

**Wrong** (pseudocode):
```
Step 1: Call the vulnerability API at /api/v1/cves?limit=20
```

## Argument Formatting

- Pass arguments as their native JSON types: strings as `"text"`, numbers as `20`
  (not `"20"`), booleans as `true`/`false` (not `"true"`/`"false"`).
- Omit optional arguments you don't need — do not pass `null` or empty strings.
- For list/array parameters, use JSON arrays: `["tag1", "tag2"]`.

## Known Filter Parameters

These parameters are confirmed from the actual MCP tool schemas — use them
directly without a schema lookup.

**`vulnerability__get_cves`**: `limit` (integer), `offset` (integer),
`sort` (string, e.g., `"-cvss_score"`),
`impact` (string — comma-separated numeric impact IDs: `"7"` for Critical,
`"5"` for Important, `"3"` for Moderate, `"1"` for Low; combine as `"5,7"`
for Important+Critical),
`known_exploit` (string: `"true"` or `"false"`),
`advisory_available` (string: `"true"` for CVEs with available advisories),
`cvss_from` / `cvss_to` (number — filter by CVSS score range),
`affecting_host_type` (string),
`filter_` (string — search/filter text).

**`vulnerability__get_system_cves`**: `system_uuid` (string, **required**),
`limit` (integer), `offset` (integer), `sort` (string),
`filter_` (string — search/filter text).

**`vulnerability__get_systems`**: `limit` (integer), `offset` (integer),
`sort` (string), `filter_` (string — search by display name or hostname),
`group_names` (string), `rhel_versions` (string).

**`inventory__list_hosts`**: `per_page` (integer, **use 10 on first call**),
`page` (integer, starts at 1 — increment for pagination),
`hostname_or_id` (string), `display_name` (string), `fqdn` (string),
`tags` (string — tag filter like `"ns/key=value"`, not an array),
`staleness` (string: `"fresh"`, `"stale"`, `"stale_warning"`, `"unknown"`),
`order_by` (string: `"display_name"`, `"updated"`, or `"created"`),
`order_how` (string: `"ASC"` or `"DESC"`).

**`inventory__get_host_system_profile`**: `host_ids` (string — comma-separated
UUIDs, **one or two at a time** due to large response size). Use this tool
when RHEL version information is needed — `list_hosts` does not reliably
include `system_profile`.

**`vulnerability__get_cve_systems`**: `cve` (string, **required** — format
`"CVE-YYYY-NNNNN"`, uppercase, not `cve_id`), `limit` (integer),
`offset` (integer), `sort` (string), `filter_` (string — filter on system
display name), `system_uuid` (string — check a specific system).

**`advisor__get_active_rules`**: `limit` (integer), `offset` (integer),
`sort` (string, e.g., `"-total_risk"` for highest-risk first),
`impacting` (string: `"true"` or `"false"` — **not boolean**, pass as string),
`incident` (string: `"true"` or `"false"`),
`has_automatic_remediation` (string: `"true"` or `"false"`),
`impact` (string — numeric risk level), `likelihood` (string — numeric),
`category` (string), `reboot` (string: `"true"` or `"false"`),
`groups` (string), `tags` (string).

**`advisor__get_recommendations_stats`**: `groups` (string), `tags` (string).

### String-typed booleans

Several MCP tools use **string** type for boolean-like parameters (e.g.,
`impacting`, `known_exploit`, `advisory_available`, `incident`). Always pass
these as the string `"true"` or `"false"` — never as JSON boolean `true`/`false`.
Passing a boolean instead of a string will cause the MCP server to reject the call.

### Multi-impact queries

The `impact` parameter accepts comma-separated numeric IDs, so you can request
multiple severity levels in a single call. For example, to get both Critical
and Important CVEs: `impact="3,4"`.

Alternatively, omit `impact` and use `sort="-cvss_score"` to surface the
highest-severity CVEs first regardless of impact level.

For parameters not listed here, call the corresponding `*_get_openapi` tool
(e.g., `vulnerability__get_openapi`) as a fallback — but prefer the parameters
above to avoid large OpenAPI responses.

## Tool Discovery

- Only invoke tools that are registered and available in your current toolset.
  Do not invent tool names or guess at tools that might exist.
- If no matching tool exists for a user request, say so clearly.
- When describing capabilities to users, use domain terms ("I can look up your
  CVE data") rather than exposing internal tool names.

## One Action Per Call

Each tool call performs exactly one action. To query CVEs for three different hosts,
make three separate tool calls — do not try to batch them unless the tool schema
explicitly supports a list of IDs.
