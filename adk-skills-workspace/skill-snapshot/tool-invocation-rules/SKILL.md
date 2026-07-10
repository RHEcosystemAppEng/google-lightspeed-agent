---
name: tool-invocation-rules
description: |
  ALWAYS load this skill before making any MCP tool call — it contains
  required type rules (string-typed booleans, correct parameter names)
  that prevent tool call rejections. Covers Vulnerability, Inventory,
  and Advisor tools. Without this skill, tool calls will fail due to
  wrong parameter names or types. [STRICT]
metadata:
  author: red-hat
  version: "1.6"
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

- Pass arguments using the types specified in the parameter list below.
  Strings as `"text"`, numbers as `20` (not `"20"`).
- **Important**: many boolean-like parameters (e.g., `impacting`, `known_exploit`,
  `advisory_available`) are typed as **string** in the MCP schema — pass these as
  `"true"` or `"false"` (strings), never as JSON `true`/`false`. See "String-typed
  booleans" below.
- Omit optional arguments you don't need — do not pass `null` or empty strings.
- For list/array parameters, use JSON arrays: `["tag1", "tag2"]`.

## Known Filter Parameters

These parameters are confirmed from the actual MCP tool schemas — use them
directly without a schema lookup.

**`vulnerability__get_cves`**: `limit` (integer), `offset` (integer),
`sort` (string, e.g., `"-cvss_score"` — **always include for "top" or severity queries**),
`impact` (string — comma-separated numeric impact IDs: `"7"` for Critical,
`"5"` for Important, `"4"` for Moderate, `"2"` for Low; combine as `"5,7"`
for Important+Critical),
`known_exploit` (string: `"true"` or `"false"`),
`advisory_available` (string: `"true"` for CVEs with available advisories —
**include by default** to restrict to actionable CVEs),
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
`order_by` (string: `"display_name"`, `"updated"`, or `"created"` —
**always include `"display_name"` for user-facing listings**),
`order_how` (string: `"ASC"` or `"DESC"` — **default to `"ASC"`**).

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

### Recommended defaults for common queries

Copy these argument sets for the most frequent query patterns:

**"Top/critical CVEs"** or any severity-filtered CVE query:
```json
vulnerability__get_cves: {"impact": "5,7", "sort": "-cvss_score", "advisory_available": "true", "limit": 20}
```

**"List my systems"** or any host/inventory listing:
```json
inventory__list_hosts: {"per_page": 10, "page": 1, "order_by": "display_name", "order_how": "ASC"}
```

**"Top advisor recommendations"** or any advisor query:
```json
advisor__get_active_rules: {"impacting": "true", "sort": "-total_risk", "limit": 20}
```

Omit filters you don't need, but always keep `sort` and `limit`/`per_page`.

### String-typed booleans — CRITICAL

These parameters look like booleans but MUST be passed as **strings**:
`impacting`, `known_exploit`, `advisory_available`, `incident`,
`has_automatic_remediation`, `reboot`.

**Correct**: `impacting="true"`, `known_exploit="false"`
**Wrong**: `impacting=true`, `known_exploit=false` (JSON booleans — will cause errors)

The MCP server rejects JSON boolean values for these parameters.

### Multi-impact queries

The `impact` parameter accepts comma-separated numeric IDs, so you can request
multiple severity levels in a single call. For example, to get both Critical
and Important CVEs: `impact="5,7"`.
For Moderate and above: `impact="4,5,7"`. For all actionable severities: `impact="2,4,5,7"`.

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
