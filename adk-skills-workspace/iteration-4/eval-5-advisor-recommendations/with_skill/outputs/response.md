# Eval 5 — "What are the top advisor recommendations for my environment?"

## With Skills

---

### 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Guides correct argument formatting and JSON types for tool calls; confirms known parameter set for `advisor__get_active_rules`. |
| **multi-step-workflows** | The query asks for "top" recommendations — the skill's workflow example for infrastructure health overview directs using `advisor__get_recommendations_stats` for a summary, plus `advisor__get_active_rules` for the detailed list. Two-tool chain is appropriate. |
| **efficient-counting** | Not directly activated for counting, but its metadata field reference (`meta.count` for advisor tools) informs how to interpret the total in the response. |
| **response-formatting** | Directs advisor recommendations to be "grouped by severity or category" with "rule description and number of affected systems." |
| **guardrails-safety** | Read-only scope applies; advisor recommendations cover configuration best practices (not CVE patching). Partial-data transparency rule applies if results are paginated. |
| **error-handling** | Standing readiness — would activate if the tool call returned an error or oversized response. |

---

### 2. Tool Calls

#### Tool Call 1: Get recommendation statistics overview

**Rationale (from multi-step-workflows):** The workflow example for "Give me an overview of my infrastructure health" starts with `advisor__get_recommendations_stats`. This gives a severity breakdown before diving into details, enabling a structured "top recommendations" answer.

```
tool: advisor__get_recommendations_stats
args: {}
```

**Simulated Response:**
```json
{
  "total_risk": {
    "4": 3,
    "3": 8,
    "2": 15,
    "1": 6
  },
  "total_rules": 32,
  "total_systems_affected": 47,
  "categories": {
    "availability": 5,
    "stability": 7,
    "performance": 9,
    "security": 11
  }
}
```

#### Tool Call 2: Get top active rules sorted by severity

**Rationale (from tool-invocation-rules):** Use native JSON types for arguments. The `sort` parameter with `-total_risk` surfaces highest-severity rules first. `limit=20` caps the response per the response-formatting inline-list cap. The `impacting=true` filter restricts to rules that actually affect systems in this environment (from the available parameter list).

```
tool: advisor__get_active_rules
args: {"sort": "-total_risk", "limit": 20, "impacting": true}
```

**Simulated Response:**
```json
{
  "meta": {
    "count": 32
  },
  "data": [
    {
      "rule_id": "hardening_ssh_root_login|HARDENING_SSH_ROOT_LOGIN",
      "description": "SSH root login is permitted on this system, which increases the risk of unauthorized remote access.",
      "total_risk": 4,
      "category": {"name": "Security"},
      "impact": {"name": "Unauthorized Access", "impact": 4},
      "likelihood": 4,
      "systems_affected": 12,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "kernel_panic_on_oops|KERNEL_PANIC_ON_OOPS",
      "description": "Kernel is not configured to panic on oops, which may leave systems in an unstable state after kernel errors.",
      "total_risk": 4,
      "category": {"name": "Stability"},
      "impact": {"name": "System Instability", "impact": 4},
      "likelihood": 3,
      "systems_affected": 18,
      "has_playbook": true,
      "reboot_required": true
    },
    {
      "rule_id": "tuned_profile_not_active|TUNED_PROFILE_NOT_ACTIVE",
      "description": "No tuned profile is active, leading to suboptimal system performance for the workload.",
      "total_risk": 4,
      "category": {"name": "Performance"},
      "impact": {"name": "Degraded Performance", "impact": 3},
      "likelihood": 4,
      "systems_affected": 9,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "chrony_not_synced|CHRONY_NOT_SYNCED",
      "description": "System clock is not synchronized via chronyd, which can cause authentication failures, certificate validation issues, and log timestamp inconsistencies.",
      "total_risk": 3,
      "category": {"name": "Availability"},
      "impact": {"name": "Authentication Failures", "impact": 3},
      "likelihood": 3,
      "systems_affected": 7,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "kdump_not_configured|KDUMP_NOT_CONFIGURED",
      "description": "Kdump is not configured, so kernel crash dumps will not be captured for post-mortem analysis.",
      "total_risk": 3,
      "category": {"name": "Stability"},
      "impact": {"name": "No Crash Diagnostics", "impact": 3},
      "likelihood": 2,
      "systems_affected": 14,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "firewalld_disabled|FIREWALLD_DISABLED",
      "description": "Firewalld is not running, leaving the system without host-based firewall protection.",
      "total_risk": 3,
      "category": {"name": "Security"},
      "impact": {"name": "Network Exposure", "impact": 3},
      "likelihood": 3,
      "systems_affected": 5,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "ntp_drift|NTP_DRIFT",
      "description": "Significant time drift detected on systems, which may impact Kerberos authentication and log correlation.",
      "total_risk": 3,
      "category": {"name": "Availability"},
      "impact": {"name": "Authentication Issues", "impact": 3},
      "likelihood": 2,
      "systems_affected": 4,
      "has_playbook": true,
      "reboot_required": false
    },
    {
      "rule_id": "auditd_not_running|AUDITD_NOT_RUNNING",
      "description": "The audit daemon is not running, so security-relevant events are not being logged.",
      "total_risk": 3,
      "category": {"name": "Security"},
      "impact": {"name": "Missing Audit Trail", "impact": 3},
      "likelihood": 3,
      "systems_affected": 6,
      "has_playbook": true,
      "reboot_required": false
    }
  ]
}
```

---

### 3. User-Facing Response

Your environment has **32 active advisor recommendations** affecting **47 systems** total. Here are the top recommendations, grouped by severity:

#### Critical Risk (3 recommendations)

| Recommendation | Category | Systems Affected | Playbook Available | Reboot Required |
|---|---|---|---|---|
| SSH root login is permitted, increasing the risk of unauthorized remote access | Security | 12 | Yes | No |
| Kernel is not configured to panic on oops, which may leave systems unstable after kernel errors | Stability | 18 | Yes | Yes |
| No tuned profile is active, leading to suboptimal system performance | Performance | 9 | Yes | No |

#### Important Risk (5 of 8 shown)

| Recommendation | Category | Systems Affected | Playbook Available | Reboot Required |
|---|---|---|---|---|
| System clock not synchronized via chronyd — can cause authentication failures and log inconsistencies | Availability | 7 | Yes | No |
| Kdump not configured — kernel crash dumps will not be captured for analysis | Stability | 14 | Yes | No |
| Firewalld is not running — no host-based firewall protection | Security | 5 | Yes | No |
| Significant time drift detected — may impact Kerberos auth and log correlation | Availability | 4 | Yes | No |
| Audit daemon not running — security-relevant events are not being logged | Security | 6 | Yes | No |

...and 3 more Important-risk recommendations. There are also 15 Moderate and 6 Low-risk recommendations.

**By category**, the breakdown is: Security (11), Performance (9), Stability (7), Availability (5).

All recommendations shown above have Ansible playbooks available for remediation. Note that the kernel panic configuration change requires a reboot. This agent operates in read-only mode — to apply remediations, use your standard change management process with the available Ansible playbooks.

Would you like me to drill into a specific recommendation to see which systems are affected, or focus on a particular category like Security?

---

## Skill Impact Analysis

| Aspect | Behavior Attributable to Skills |
|---|---|
| **Two-tool workflow** | `multi-step-workflows` directed using `advisor__get_recommendations_stats` first for the summary, then `advisor__get_active_rules` for details — rather than a single call. |
| **Argument formatting** | `tool-invocation-rules` ensured `impacting=true` (boolean), `limit=20` (integer), and `sort="-total_risk"` (string) used correct JSON types. |
| **Grouped-by-severity presentation** | `response-formatting` explicitly says advisor recommendations should be "grouped by severity or category" with "rule description and number of affected systems." |
| **"32 active recommendations affecting 47 systems"** | `efficient-counting` informed reading `meta.count` from the advisor response for the total, and the stats call provided affected-system totals. |
| **"...and 3 more" with offer to filter** | `response-formatting` caps inline lists at 20 items and adds a summary line. Applied at the Important-risk group level. |
| **Read-only caveat** | `guardrails-safety` mandates explaining that the agent operates in read-only mode when remediation is mentioned. |
| **Paginated transparency** | `guardrails-safety` partial-data transparency rule drove stating "5 of 8 shown" for the Important-risk group. |
| **No self-introduction** | `response-formatting` says "do not open with a self-introduction or greeting" — response jumps straight to the data. |
