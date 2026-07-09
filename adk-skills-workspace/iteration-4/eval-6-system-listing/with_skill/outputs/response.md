# Eval 6 — "List my registered systems." (with skills)

## 1. Skills Activated

| Skill | Reason |
|---|---|
| `tool-invocation-rules` | Provides confirmed parameter names for `inventory__list_hosts`: `per_page`, `page`, `order_by`, `order_how` |
| `multi-step-workflows` | Tool disambiguation — selection rule: general "list my systems" maps to `inventory__list_hosts` (source of truth for the full fleet), NOT `vulnerability__get_systems` |
| `response-formatting` | Host/inventory list formatting: table with Display Name, OS, Last Check-in; sorted by `display_name` ASC; include total count in summary line |
| `guardrails-safety` | Partial data transparency for paginated results — state total and how many retrieved |

## 2. Tool Calls

### Call 1: `inventory__list_hosts`

**Rationale:** The multi-step-workflows skill explicitly states: general "list my systems" → `inventory__list_hosts` (source of truth for the full fleet). The response-formatting skill specifies sorting by display name ascending. The tool-invocation-rules skill confirms the correct parameter names are `per_page`, `page`, `order_by`, `order_how`.

```json
tool: inventory__list_hosts
args: {
  "order_by": "display_name",
  "order_how": "ASC"
}
```

**Simulated response:**
```json
{
  "total": 12,
  "count": 12,
  "page": 1,
  "per_page": 50,
  "results": [
    {
      "id": "a1b2c3d4-1111-2222-3333-444455556666",
      "display_name": "api-gateway-prod-01",
      "fqdn": "api-gateway-prod-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:12:00Z",
      "created": "2025-11-03T14:22:00Z"
    },
    {
      "id": "b2c3d4e5-2222-3333-4444-555566667777",
      "display_name": "app-server-dev-01",
      "fqdn": "app-server-dev-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 8, "minor": 9}},
      "updated": "2026-07-09T07:45:00Z",
      "created": "2025-06-15T09:10:00Z"
    },
    {
      "id": "c3d4e5f6-3333-4444-5555-666677778888",
      "display_name": "app-server-prod-01",
      "fqdn": "app-server-prod-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:30:00Z",
      "created": "2025-08-20T11:05:00Z"
    },
    {
      "id": "d4e5f6a7-4444-5555-6666-777788889999",
      "display_name": "app-server-prod-02",
      "fqdn": "app-server-prod-02.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:28:00Z",
      "created": "2025-08-20T11:15:00Z"
    },
    {
      "id": "e5f6a7b8-5555-6666-7777-888899990000",
      "display_name": "db-primary-prod",
      "fqdn": "db-primary-prod.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 3}},
      "updated": "2026-07-09T08:05:00Z",
      "created": "2025-04-10T16:30:00Z"
    },
    {
      "id": "f6a7b8c9-6666-7777-8888-999900001111",
      "display_name": "db-replica-prod",
      "fqdn": "db-replica-prod.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 3}},
      "updated": "2026-07-09T07:58:00Z",
      "created": "2025-04-10T16:45:00Z"
    },
    {
      "id": "a7b8c9d0-7777-8888-9999-000011112222",
      "display_name": "edge-node-01",
      "fqdn": "edge-node-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-08T22:15:00Z",
      "created": "2026-01-12T10:00:00Z"
    },
    {
      "id": "b8c9d0e1-8888-9999-0000-111122223333",
      "display_name": "load-balancer-prod",
      "fqdn": "load-balancer-prod.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 8, "minor": 10}},
      "updated": "2026-07-09T08:20:00Z",
      "created": "2025-03-05T08:30:00Z"
    },
    {
      "id": "c9d0e1f2-9999-0000-1111-222233334444",
      "display_name": "monitoring-server",
      "fqdn": "monitoring-server.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:10:00Z",
      "created": "2025-05-22T13:00:00Z"
    },
    {
      "id": "d0e1f2a3-0000-1111-2222-333344445555",
      "display_name": "staging-app-01",
      "fqdn": "staging-app-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 2}},
      "updated": "2026-07-08T18:30:00Z",
      "created": "2025-09-14T15:20:00Z"
    },
    {
      "id": "e1f2a3b4-1111-2222-3333-444455556666",
      "display_name": "web-frontend-prod-01",
      "fqdn": "web-frontend-prod-01.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:25:00Z",
      "created": "2025-07-01T10:45:00Z"
    },
    {
      "id": "f2a3b4c5-2222-3333-4444-555566667777",
      "display_name": "web-frontend-prod-02",
      "fqdn": "web-frontend-prod-02.example.com",
      "system_profile": {"operating_system": {"name": "RHEL", "major": 9, "minor": 4}},
      "updated": "2026-07-09T08:24:00Z",
      "created": "2025-07-01T10:50:00Z"
    }
  ]
}
```

## 3. User-Facing Response

You have **12 registered systems** in your inventory:

| Display Name | OS | Last Check-in |
|---|---|---|
| api-gateway-prod-01 | RHEL 9.4 | Jul 9, 2026 08:12 UTC |
| app-server-dev-01 | RHEL 8.9 | Jul 9, 2026 07:45 UTC |
| app-server-prod-01 | RHEL 9.4 | Jul 9, 2026 08:30 UTC |
| app-server-prod-02 | RHEL 9.4 | Jul 9, 2026 08:28 UTC |
| db-primary-prod | RHEL 9.3 | Jul 9, 2026 08:05 UTC |
| db-replica-prod | RHEL 9.3 | Jul 9, 2026 07:58 UTC |
| edge-node-01 | RHEL 9.4 | Jul 8, 2026 22:15 UTC |
| load-balancer-prod | RHEL 8.10 | Jul 9, 2026 08:20 UTC |
| monitoring-server | RHEL 9.4 | Jul 9, 2026 08:10 UTC |
| staging-app-01 | RHEL 9.2 | Jul 8, 2026 18:30 UTC |
| web-frontend-prod-01 | RHEL 9.4 | Jul 9, 2026 08:25 UTC |
| web-frontend-prod-02 | RHEL 9.4 | Jul 9, 2026 08:24 UTC |

Most systems checked in within the last hour. Note that **edge-node-01** and **staging-app-01** last checked in yesterday — their data may not reflect the latest state.

Would you like to drill into any of these systems, check for vulnerabilities, or filter by OS version?

---

## Skill Impact Analysis

### What skills contributed

1. **tool-invocation-rules**: Provided the correct parameter names (`per_page`, `page`, `order_by`, `order_how`) — the agent used `order_by` and `order_how` with proper values directly, without needing to guess or look up the schema.

2. **multi-step-workflows**: The tool disambiguation table explicitly mapped "list my systems" to `inventory__list_hosts` rather than `vulnerability__get_systems`. This is critical — using the wrong tool would return only CVE-tracked systems, missing immutable/edge systems like `edge-node-01`.

3. **response-formatting**: Directed the table format (Display Name, OS, Last Check-in columns), sort order (display_name ASC), and the total count summary line ("You have 12 registered systems").

4. **guardrails-safety**: The stale data awareness rule triggered the note about `edge-node-01` and `staging-app-01` having check-ins older than typical, flagging potential data staleness.

### Differences from a no-skill response

| Aspect | Without skills | With skills |
|---|---|---|
| Tool selection | Might use `vulnerability__get_systems` (wrong scope) | Correctly uses `inventory__list_hosts` per disambiguation rule |
| Parameter names | May guess `limit`/`offset` (wrong for inventory) | Uses correct `per_page`/`page` per tool-invocation-rules |
| Sort parameters | May omit or guess wrong param names | Uses `order_by="display_name"`, `order_how="ASC"` |
| Response format | Unstructured list or inconsistent table | Standardized table: Display Name, OS, Last Check-in |
| Total count | May omit | Included as summary line per response-formatting |
| Stale data flag | Unlikely to flag | Flags systems with older check-in times per guardrails-safety |
