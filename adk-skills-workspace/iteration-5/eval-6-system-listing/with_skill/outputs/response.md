# Response: "List my registered systems"

## Plan

This is a straightforward single-tool request. Per the **multi-step-workflows** skill, "list my systems" maps directly to `inventory__list_hosts`, which is the source of truth for the full fleet of registered systems. No multi-step chaining is needed.

## Step-by-Step Tool Calls

### Step 1 (only step): Fetch the first page of registered systems

**Tool:** `inventory__list_hosts`
**Arguments:**
```json
{
  "per_page": 10,
  "page": 1,
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Reasoning:**

- **Tool selection:** The multi-step-workflows skill explicitly states: *"General 'how many systems/hosts?' or 'list my systems' -> `inventory__list_hosts` (source of truth for the full fleet)."* The alternative `vulnerability__get_systems` only returns systems tracked for CVE analysis and excludes immutable/edge systems, so it would give an incomplete picture.
- **`per_page=10`:** The tool-invocation-rules skill mandates: *"use 10 on first call"* for `per_page`. This keeps the response manageable and avoids oversized results.
- **`page=1`:** Start at the first page of results.
- **`order_by="display_name"`:** The tool-invocation-rules skill requires: *"always include `display_name` for user-facing listings."*
- **`order_how="ASC"`:** The tool-invocation-rules skill says to *"default to `ASC`"*, and the response-formatting skill confirms host lists should be sorted by display name ascending.
- **No extra filters:** The user asked for all registered systems without any narrowing criteria (no RHEL version, no staleness filter, no hostname search), so no additional parameters are needed. Optional arguments are omitted per the tool-invocation-rules skill: *"Omit optional arguments you don't need -- do not pass null or empty strings."*

### After receiving the response

1. **Read the `total` field** from the response metadata to know the full count of registered systems (per the efficient-counting skill, the `total` field in the Inventory API response gives the total without needing to paginate through all pages).

2. **Format the results as a table** with columns: Display Name, OS (e.g., RHEL 8.9), Last Check-in -- as specified by the response-formatting skill for host/inventory lists.

3. **Include a summary line** with the total count, e.g., "Showing 10 of 142 registered systems."

4. **If more than 20 systems exist**, the response-formatting skill caps inline lists at 20 items. So if `total` is greater than 20, show the first page (10 systems) and add: *"...and N more. Ask me to continue or apply filters to narrow down."*

5. **If `total` is between 11 and 20**, make one additional call to fetch page 2:
   ```json
   {
     "per_page": 10,
     "page": 2,
     "order_by": "display_name",
     "order_how": "ASC"
   }
   ```
   This retrieves all systems within the 20-item display cap.

### Error handling

- If the tool returns a `tool_result_too_large` error, reduce `per_page` to 5 and retry (per the error-handling skill's first strategy: reduce page size).
- If the tool returns a 401/403, inform the user to re-authenticate or check RBAC permissions.
- If the tool returns zero results, report this as a valid finding: "No registered systems were found in your inventory."
- If the tool returns a 500/502/503, retry once before reporting the service as temporarily unavailable.

## What I Would NOT Do

- **Would not use `vulnerability__get_systems`:** That endpoint only returns systems tracked for CVE analysis and excludes immutable systems. The user asked for "registered systems," which maps to the full inventory.
- **Would not use `limit=1` for counting only:** The user asked to "list" systems, not just count them. They want to see the actual systems.
- **Would not fetch all pages at once:** Start with `per_page=10` on the first call, respect the 20-item cap, and offer to continue if there are more.
- **Would not generate code or pseudocode:** The tool-invocation-rules skill requires actual tool calls, not Python snippets or API URL references.

## Example Formatted Output

After the tool call returns, the response to the user would look like:

---

You have **142** registered systems. Here are the first 10:

| Display Name | OS | Last Check-in |
|---|---|---|
| app-server-01.example.com | RHEL 9.3 | 2026-07-09 |
| app-server-02.example.com | RHEL 9.3 | 2026-07-09 |
| db-primary.example.com | RHEL 8.9 | 2026-07-08 |
| ... | ... | ... |

...and 132 more. Ask me to continue or apply filters to narrow down (e.g., by RHEL version or staleness).

---
