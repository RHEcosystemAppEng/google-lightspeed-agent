---
name: error-handling
description: |
  Recovering from tool call failures, oversized responses, and HTTP errors.
  Use this skill when a tool call returns an error, times out, returns
  too much data, or produces an unexpected HTTP status code. Covers retry
  strategies, narrowing queries, and interpreting error codes. [PREFERRED]
metadata:
  author: red-hat
  version: "1.0"
---

## Handling Oversized Tool Results [PREFERRED]

If a tool call returns a `tool_result_too_large` error, the result was too large to
process. Do NOT tell the user the tool failed — instead, automatically retry with a
narrower query. Apply these strategies in order:

1. **Reduce page size**: If the tool supports `limit`/`per_page`, reduce it
(e.g., from 100 to 20).
2. **Add filters**: Apply severity, date range, status, or other filters to narrow
the result set (e.g., `severity=Critical`, `status=Applicable`).
3. **Scope to specific systems**: Instead of querying all systems, target a specific
host or group.
4. **Filter fields**: If the tool supports field selection, request only the fields
relevant to the user's question plus IDs needed for follow-up queries. Drop
unnecessary fields to reduce the response size.
5. **Ask the user**: If none of the above strategies can be applied automatically,
explain that the result set is very large and ask the user to narrow their request
(e.g., by specifying a host, severity, or date range).

Example: If `get_cves` returns `tool_result_too_large`, retry with
`limit=20, severity=Critical` before falling back to asking the user.

## Handling Tool Errors [PREFERRED]

When a tool call fails, interpret the error and respond appropriately:

- **401 / 403 (authentication or authorization)**: The user's token may have expired
or their account may lack the required permissions. Tell the user to re-authenticate
or check their RBAC permissions for the requested resource.
- **404 (not found)**: The requested resource (host, CVE, etc.) does not exist or is
not visible to the user's organization. State this clearly — do not retry.
- **429 (rate limited)**: The API is temporarily throttling requests. Wait briefly,
then retry once. If it fails again, tell the user to try again shortly.
- **500 / 502 / 503 (server error)**: The backend service is having issues. Retry
once. If it fails again, tell the user the service is temporarily unavailable and
suggest trying again later.
- **Timeout / connection error**: Retry once. If it fails again, report that the
service is not responding.
- **Empty results vs. errors**: Distinguish between "no data found" (which can be
good news, e.g., zero critical CVEs) and "the API call failed." Report empty
results as a finding, not as a failure.

Do NOT silently swallow errors or tell the user "I couldn't find anything" when
the real problem was an API failure. Be transparent about what went wrong.
