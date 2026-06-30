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
  version: "1.2"
---

## Invocation Format

Capabilities are exposed as MCP tools. Each action is a separate function call
with JSON arguments. Do not output Python, shell scripts, or pseudocode instead
of making an actual tool call — even when describing a multi-step plan.

**Correct:**
```
tool: vulnerability__get_cves
args: {"limit": 20, "severity": "Critical", "sort": "-cvss_score"}
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

These parameters are confirmed available — use them directly without a schema lookup.

**`vulnerability__get_cves`**: `limit`, `offset`, `sort` (e.g., `-cvss_score`),
`severity` (Critical, Important, Moderate, Low), `known_exploit` (true/false),
`affecting` (true/false — only CVEs affecting at least one system).

**`vulnerability__get_system_cves`**: `limit`, `offset`, `sort`,
`severity` (Critical, Important, Moderate, Low), `known_exploit` (true/false),
`status` (Applicable, Not applicable), `remediation`
(Applicable — has a remediation available).

**`vulnerability__get_systems`**: `limit`, `offset`, `sort`,
`filter` (search string for display name or hostname).

**`inventory__list_hosts`**: `limit`, `offset`, `hostname_or_id`,
`display_name`, `tags`, `operating_system`, `order_by`, `order_how` (ASC/DESC).

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
