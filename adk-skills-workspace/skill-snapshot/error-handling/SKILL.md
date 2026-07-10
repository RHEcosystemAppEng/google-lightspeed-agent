---
name: error-handling
description: |
  Recovering from tool call failures, oversized responses, and HTTP errors.
  Use this skill when a tool call returns an error, times out, returns
  too much data, or produces an unexpected HTTP status code. Covers retry
  strategies, narrowing queries, and interpreting error codes. [PREFERRED]
metadata:
  author: red-hat
  version: "1.2"
---

## Oversized Tool Results

If a tool call returns a `tool_result_too_large` error, the result was too large to
process. Do NOT tell the user the tool failed — instead, automatically retry with a
narrower query. Apply these strategies in order:

1. **Reduce page size**: If the tool supports `limit`/`per_page`, reduce it
   (e.g., from 100 to 20).
2. **Add filters**: Apply impact level, date range, or other filters to narrow
   the result set (e.g., `impact="7"` for Critical-only, `advisory_available="true"`).
3. **Scope to specific systems**: Instead of querying all systems, target a specific
   host or group.
4. **Filter fields**: If the tool supports field selection, request only the fields
   relevant to the user's question plus IDs needed for follow-up queries.
5. **Ask the user**: If none of the above strategies work automatically,
   explain that the result set is very large and ask the user to narrow their request.

Example: If `vulnerability__get_cves` returns `tool_result_too_large`, retry with
`limit=20, impact="7"` before falling back to asking the user.

## HTTP Status Codes

When a tool call fails, interpret the error and respond appropriately:

| Status | Meaning | Action |
|---|---|---|
| 401 / 403 | Authentication or authorization failure | Tell the user to re-authenticate or check RBAC permissions. Do not retry. |
| 404 | Resource not found | State clearly that the resource was not found. Do not retry or guess similar IDs. |
| 429 | Rate limited | Retry once after a brief pause. If it fails again, tell the user to try again shortly. |
| 500 / 502 / 503 | Server error | Retry once. If it fails again, report the service is temporarily unavailable. |

## Connection and Timeout Errors

- **Timeout**: Retry once. If it fails again, report that the service is not responding.
- **MCP connection failure**: If the MCP server itself is unreachable (as opposed to
  the upstream Insights API returning an error), report that the tool backend is
  unavailable. Do not retry indefinitely — one retry is sufficient.

## Malformed or Unexpected Responses

If a tool returns data in an unexpected shape (missing expected fields, wrong types,
or truncated JSON), do not attempt to guess the missing data. Report what you received,
note what was unexpected, and suggest the user retry. This is different from an empty
result — an empty result is a valid finding (e.g., zero critical CVEs).

## Empty Results vs. Errors

Distinguish between "no data found" (which can be good news, e.g., zero critical CVEs)
and "the API call failed." Report empty results as a finding, not as a failure. For
example: "No critical CVEs were found affecting host X" is useful information.

Never silently swallow errors or tell the user "I couldn't find anything" when
the real problem was an API failure. Be transparent about what went wrong.
