# Eval 5 — "What are the top advisor recommendations for my environment?" (Old Skills)

## 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Correct argument formatting for advisor tool calls |
| **multi-step-workflows** | Chaining advisor stats + active rules + host details across multiple calls |
| **response-formatting** | Formatting advisor recommendations grouped by severity with affected system counts |
| **guardrails-safety** | Partial data transparency — noting pagination limits and data freshness |
| **error-handling** | Standby for oversized responses or API failures |

**efficient-counting** is not directly activated — this is a "show me" query, not a "how many" query.

## 2. Tool Calls

### Call 1: Get recommendation statistics overview

```
tool: advisor__get_recommendations_stats
args: {}
```

**Simulated response:**
```json
{
  "total_risk": {
    "1": 12,
    "2": 45,
    "3": 18,
    "4": 5
  },
  "category": {
    "Availability": 22,
    "Performance": 15,
    "Security": 28,
    "Stability": 15
  },
  "total": 80,
  "systems_with_hits": 37
}
```

### Call 2: Get active rules sorted by highest risk, limited to top results

```
tool: advisor__get_active_rules
args: {"limit": 20, "sort": "-total_risk"}
```

**Simulated response:**
```json
{
  "meta": {
    "count": 80,
    "limit": 20,
    "offset": 0
  },
  "data": [
    {
      "rule_id": "network_bond_opts_config_issue|NETWORK_BONDING_OPTS_DOUBLE_QUOTES_ISSUE",
      "description": "Bonding configuration uses incorrect quoting for BONDING_OPTS, which may cause network interfaces to fail on reboot.",
      "total_risk": 4,
      "category": { "name": "Availability" },
      "impact": { "name": "Network Connectivity Loss", "impact": 4 },
      "likelihood": 4,
      "systems_affected": 8,
      "has_playbook": true
    },
    {
      "rule_id": "hardening_sshd_config|HARDENING_SSHD_PERMIT_ROOT",
      "description": "SSH daemon is configured to permit root login, which increases the attack surface for unauthorized access.",
      "total_risk": 4,
      "category": { "name": "Security" },
      "impact": { "name": "Unauthorized Access", "impact": 4 },
      "likelihood": 3,
      "systems_affected": 14,
      "has_playbook": true
    },
    {
      "rule_id": "kernel_panic_sysctl|KERNEL_PANIC_REBOOT_NOT_SET",
      "description": "Systems do not automatically reboot after a kernel panic, potentially causing extended unplanned downtime.",
      "total_risk": 4,
      "category": { "name": "Stability" },
      "impact": { "name": "Extended Downtime", "impact": 4 },
      "likelihood": 3,
      "systems_affected": 11,
      "has_playbook": true
    },
    {
      "rule_id": "CVE_2024_6387_sshd|CVE_2024_6387_SSHD_RACE",
      "description": "OpenSSH versions are affected by CVE-2024-6387 (regreSSHion), a remote code execution vulnerability in sshd.",
      "total_risk": 4,
      "category": { "name": "Security" },
      "impact": { "name": "Remote Code Execution", "impact": 4 },
      "likelihood": 4,
      "systems_affected": 6,
      "has_playbook": true
    },
    {
      "rule_id": "tuned_profile_mismatch|TUNED_PROFILE_NOT_ACTIVE",
      "description": "The recommended tuned profile is not active, which may result in suboptimal system performance.",
      "total_risk": 3,
      "category": { "name": "Performance" },
      "impact": { "name": "Degraded Performance", "impact": 3 },
      "likelihood": 3,
      "systems_affected": 9,
      "has_playbook": true
    }
  ]
}
```

No further chained calls are made. The top rules already include `systems_affected` counts, so drilling into `advisor__get_hosts_hitting_a_rule` would only be warranted if the user asks about a specific recommendation.

## 3. User-Facing Response

---

Your environment has **80 active advisor recommendations** across **37 systems**. Here is a breakdown by category and the highest-priority items to address.

### Recommendation Summary

| Category | Count |
|---|---|
| Security | 28 |
| Availability | 22 |
| Performance | 15 |
| Stability | 15 |

By risk level: **5 critical**, 18 important, 45 moderate, and 12 low.

### Top Recommendations (Highest Risk)

| # | Recommendation | Category | Risk | Affected Systems | Playbook |
|---|---|---|---|---|---|
| 1 | Bonding configuration uses incorrect quoting for BONDING_OPTS — network interfaces may fail on reboot | Availability | Critical | 8 | Yes |
| 2 | SSH daemon permits root login, increasing the attack surface for unauthorized access | Security | Critical | 14 | Yes |
| 3 | Systems do not auto-reboot after kernel panic, risking extended unplanned downtime | Stability | Critical | 11 | Yes |
| 4 | OpenSSH affected by CVE-2024-6387 (regreSSHion) — remote code execution vulnerability | Security | Critical | 6 | Yes |
| 5 | Recommended tuned profile is not active, causing suboptimal performance | Performance | Important | 9 | Yes |

...and 75 more. Ask me to continue or filter by category (e.g., "show me only security recommendations").

All five critical recommendations have Ansible playbooks available for remediation. I'd suggest prioritizing **#2 (SSH root login)** and **#4 (CVE-2024-6387)** first given their security impact across 14 and 6 systems respectively.

Would you like me to show the affected systems for any of these recommendations, or drill into a specific category?

---

## Evaluation Notes

**Skills behavior:**
- **tool-invocation-rules**: Arguments passed as native JSON types; `limit` as integer, `sort` as string. No pseudocode generated.
- **multi-step-workflows**: Two-call chain: stats first for the overview, then active rules for the details. The agent correctly chose `advisor__get_recommendations_stats` + `advisor__get_active_rules` rather than trying a single tool.
- **response-formatting**: Advisor recommendations grouped by severity, table includes rule description and affected systems count, capped at 5 items with "and 75 more" continuation prompt. Summary paragraph leads, then labeled sections.
- **guardrails-safety**: Partial data transparency applied — "Showing top 5 of 80" with invitation to continue or filter. Read-only posture maintained — suggested remediation via existing playbooks, not direct action.
- **error-handling**: No errors encountered in this simulation; the skill was on standby.

**Potential gaps identified:**
- The old skills do not provide specific guidance on how to sort or prioritize advisor rules (e.g., `sort=-total_risk`). The agent inferred this from parameter naming conventions.
- No skill explicitly maps the `total_risk` numeric values (1-4) to human-readable labels (Low/Moderate/Important/Critical). The agent had to infer this mapping.
- The response-formatting skill says "group by severity or category" for advisor recommendations but does not specify which is preferred or when to use which grouping strategy.
