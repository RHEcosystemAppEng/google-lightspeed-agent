---
name: tool-invocation-rules
description: |
  Correct syntax and argument formatting for calling Red Hat Insights
  MCP tools. Use this skill when invoking a tool for the first time,
  when unsure about argument format or required parameters, or when a
  tool call was rejected due to malformed input. [STRICT]
metadata:
  author: red-hat
  version: "1.1"
---

## Tool Invocation — Extended Rules [STRICT]

In addition to the base tool invocation format in the system prompt, follow these
detailed rules and examples.

### Correct vs. Incorrect Invocation

**Correct** — a single function call with JSON arguments:
```
tool: vulnerability__get_cves
args: {"limit": 20, "severity": "Critical", "sort": "-cvss_score"}
```

**Incorrect** — generating code that would call the API:
```python
# NEVER do this:
response = default_api.get_cves(limit=20, severity="Critical")
for cve in response.data:
    print(cve.id)
```

**Incorrect** — pseudocode or instructional text:
```
Step 1: Call the vulnerability API at /api/v1/cves?limit=20
Step 2: Parse the JSON response...
```

Even when describing a multi-step plan to the user, execute each step as an actual
tool call — do not write out what the calls "would look like."

### Argument Formatting

- Pass arguments as their native JSON types: strings as `"text"`, numbers as `20`
(not `"20"`), booleans as `true`/`false` (not `"true"`/`"false"`).
- Omit optional arguments you don't need — do not pass them as `null` or empty
strings unless the schema specifically requires it.
- For list/array parameters, use JSON arrays: `["tag1", "tag2"]`, not
comma-separated strings.

### Schema Lookup

If you're unsure about a tool's parameters, call the corresponding
`*_get_openapi` tool (e.g., `vulnerability__get_openapi`) to retrieve the schema.
Prefer this over guessing parameter names or types. However, for well-known
parameters documented in the `multi-step-workflows` skill (like `limit`, `offset`,
`severity`, `sort`), use them directly without a schema lookup.

### Tool Discovery

- Only invoke tools that are registered and available in your current toolset.
Do not invent tool names or guess at tools that might exist.
- If a user asks for something and no matching tool exists, say so clearly rather
than attempting a plausible-sounding tool name.
- When describing your capabilities to users, use domain terms ("I can look up
your CVE data" or "I can check your host inventory") rather than exposing internal
tool names.

### One Action Per Call

Each tool call performs exactly one action. To query CVEs for three different hosts,
make three separate tool calls — do not try to batch them into a single call unless
the tool schema explicitly supports a list of host IDs.
