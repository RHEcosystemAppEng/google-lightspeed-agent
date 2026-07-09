# Eval 6 — "List my registered systems." (old_skill / snapshot)

## 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Determines correct tool name and parameter syntax for `inventory__list_hosts` |
| **multi-step-workflows** | Tool selection: "list my systems" maps to `inventory__list_hosts` (source of truth for the full fleet); single-tool query, no chaining needed |
| **response-formatting** | Host/inventory lists: table with Display Name, OS, Last Check-in; total count summary; cap at 20 items |
| **guardrails-safety** | Partial data transparency: state total vs. retrieved count for paginated results |

## 2. Tool Calls

### Call 1: `inventory__list_hosts`

**Args:**
```json
{"limit": 20}
```

**Parameter note:** The snapshot skill documents `limit` and `offset` as the inventory parameters. These are the WRONG parameter names — the actual API uses `per_page` and `page`. This call will either fail with an invalid parameter error or the parameters will be silently ignored, returning the API's default page size instead.

**Simulated response:**
```json
{
  "total": 5,
  "count": 5,
  "results": [
    {
      "id": "a1b2c3d4-1111-2222-3333-444455556666",
      "display_name": "prod-web-01.example.com",
      "fqdn": "prod-web-01.example.com",
      "os": "RHEL 9.4",
      "last_seen": "2026-07-09T08:15:00Z",
      "system_profile": {"os_release": "9.4"}
    },
    {
      "id": "b2c3d4e5-2222-3333-4444-555566667777",
      "display_name": "prod-web-02.example.com",
      "fqdn": "prod-web-02.example.com",
      "os": "RHEL 9.4",
      "last_seen": "2026-07-09T07:45:00Z",
      "system_profile": {"os_release": "9.4"}
    },
    {
      "id": "c3d4e5f6-3333-4444-5555-666677778888",
      "display_name": "db-primary.example.com",
      "fqdn": "db-primary.example.com",
      "os": "RHEL 8.10",
      "last_seen": "2026-07-09T08:10:00Z",
      "system_profile": {"os_release": "8.10"}
    },
    {
      "id": "d4e5f6a7-4444-5555-6666-777788889999",
      "display_name": "staging-app-01.example.com",
      "fqdn": "staging-app-01.example.com",
      "os": "RHEL 9.3",
      "last_seen": "2026-07-08T14:30:00Z",
      "system_profile": {"os_release": "9.3"}
    },
    {
      "id": "e5f6a7b8-5555-6666-7777-888899990000",
      "display_name": "edge-node-03.example.com",
      "fqdn": "edge-node-03.example.com",
      "os": "RHEL 9.4",
      "last_seen": "2026-07-07T22:00:00Z",
      "system_profile": {"os_release": "9.4"}
    }
  ]
}
```

## 3. User-Facing Response

You have **5 registered systems** in your inventory:

| Display Name | OS | Last Check-in |
|---|---|---|
| prod-web-01.example.com | RHEL 9.4 | 2026-07-09 08:15 UTC |
| prod-web-02.example.com | RHEL 9.4 | 2026-07-09 07:45 UTC |
| db-primary.example.com | RHEL 8.10 | 2026-07-09 08:10 UTC |
| staging-app-01.example.com | RHEL 9.3 | 2026-07-08 14:30 UTC |
| edge-node-03.example.com | RHEL 9.4 | 2026-07-07 22:00 UTC |

Note that **edge-node-03** last checked in over 24 hours ago — its data may not reflect the current state.

Would you like details on any specific system, or would you like to check vulnerabilities affecting these hosts?

---

## Analysis: Parameter Bug Impact

The snapshot skills document `inventory__list_hosts` with parameters `limit` and `offset`. These are the **wrong parameter names** — the actual Inventory API uses `per_page` and `page`.

**Impact on this query:**
- The agent passes `{"limit": 20}` — an unrecognized parameter.
- **Best case:** The API silently ignores `limit` and returns results with its default page size (likely 50). For small inventories (under 50 systems) the user still sees all systems, masking the bug.
- **Worst case:** The API rejects the request with a validation error, and the agent must fall back or report a failure.
- **Pagination scenario:** For a user with hundreds of systems wanting to page through results, passing `offset` instead of `page` would return wrong pages or errors, making pagination broken.

The efficient-counting skill compounds this: it recommends `limit=1` for counting, which would also be sent as the wrong parameter name.
