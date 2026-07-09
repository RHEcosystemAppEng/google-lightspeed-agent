# Eval 5: "What are the top advisor recommendations for my environment?" — With Skills

## 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Ensures correct argument formatting and JSON types for advisor MCP tool calls. Prevents generating pseudocode instead of actual tool invocations. |
| **multi-step-workflows** | The query maps to a multi-step workflow: first get stats for an overview, then retrieve the actual active rules with details. The "infrastructure health" workflow example explicitly includes `advisor__get_recommendations_stats` as a first step. |
| **response-formatting** | Advisor recommendations must be "grouped by severity or category" with "rule description and number of affected systems" per the formatting skill. |
| **guardrails-safety** | Partial data transparency rules apply — must state how many recommendations are shown vs. total. Modification requests (e.g., "fix these") must be redirected to read-only analysis. |
| **efficient-counting** | Not primary, but informs the approach: advisor uses `meta.count` for totals, so we know how to read the total from the stats/rules response metadata. |
| **error-handling** | Standby — would activate if any tool call fails or returns oversized results. |

## 2. Tool Calls

### Step 1: Get Advisor Recommendations Statistics

**Rationale:** Start with the stats endpoint to get an overview of total recommendations and severity breakdown. This follows the multi-step-workflows pattern for "infrastructure health" queries.

```
tool: advisor__get_recommendations_stats
args: {}
```

**Simulated Response:**
```json
{
  "total_risk": {
    "1": 12,
    "2": 28,
    "3": 15,
    "4": 7
  },
  "total": 62,
  "category": {
    "Availability": 14,
    "Performance": 11,
    "Security": 19,
    "Stability": 18
  },
  "by_severity": {
    "critical": 7,
    "important": 15,
    "moderate": 28,
    "low": 12
  }
}
```

### Step 2: Get Active Advisor Rules (Top by Total Risk)

**Rationale:** Retrieve the actual rules sorted by highest total risk to show the "top" recommendations. Use `limit=20` to stay within inline list caps per response-formatting skill, and `sort=-total_risk` to surface the most impactful rules first.

```
tool: advisor__get_active_rules
args: {"limit": 20, "sort": "-total_risk"}
```

**Simulated Response:**
```json
{
  "meta": {
    "count": 62,
    "limit": 20,
    "offset": 0
  },
  "data": [
    {
      "rule_id": "network_bond_opts_config_issue|NETWORK_BONDING_OPTS_DOUBLE_QUOTES_ISSUE",
      "description": "Bonding configuration uses improperly quoted options, which may cause network interface failover to malfunction.",
      "category": { "name": "Availability" },
      "total_risk": 4,
      "risk_of_change": 1,
      "impact": { "name": "Network Connectivity Loss", "impact": 4 },
      "likelihood": 4,
      "hosts_acked_count": 0,
      "impacted_systems_count": 23,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-09-12T00:00:00Z"
    },
    {
      "rule_id": "hardening_ssh_ciphers|SSH_CIPHERS_WEAK_ALGORITHMS",
      "description": "SSH service is configured to allow weak cryptographic ciphers, increasing the risk of unauthorized access through cryptographic attacks.",
      "category": { "name": "Security" },
      "total_risk": 4,
      "risk_of_change": 2,
      "impact": { "name": "Unauthorized Access", "impact": 4 },
      "likelihood": 3,
      "hosts_acked_count": 0,
      "impacted_systems_count": 18,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-06-15T00:00:00Z"
    },
    {
      "rule_id": "kernel_panic_on_warn|KERNEL_PANIC_ON_WARN_ENABLED",
      "description": "Kernel parameter panic_on_warn is enabled, which causes unnecessary system reboots on non-fatal kernel warnings.",
      "category": { "name": "Stability" },
      "total_risk": 4,
      "risk_of_change": 1,
      "impact": { "name": "Unplanned Downtime", "impact": 4 },
      "likelihood": 3,
      "hosts_acked_count": 2,
      "impacted_systems_count": 15,
      "playbook_count": 1,
      "reboot_required": true,
      "publish_date": "2025-03-20T00:00:00Z"
    },
    {
      "rule_id": "tuned_profile_mismatch|TUNED_PROFILE_NOT_ACTIVE",
      "description": "The active tuned profile does not match the recommended profile for the system's workload, resulting in suboptimal performance.",
      "category": { "name": "Performance" },
      "total_risk": 3,
      "risk_of_change": 1,
      "impact": { "name": "Degraded Performance", "impact": 3 },
      "likelihood": 4,
      "hosts_acked_count": 0,
      "impacted_systems_count": 31,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-08-02T00:00:00Z"
    },
    {
      "rule_id": "yum_dnf_repo_gpgcheck|DNF_REPO_GPGCHECK_DISABLED",
      "description": "One or more DNF/YUM repositories have GPG signature verification disabled, allowing potentially tampered packages to be installed.",
      "category": { "name": "Security" },
      "total_risk": 3,
      "risk_of_change": 1,
      "impact": { "name": "Package Integrity Risk", "impact": 3 },
      "likelihood": 3,
      "hosts_acked_count": 0,
      "impacted_systems_count": 14,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-07-18T00:00:00Z"
    },
    {
      "rule_id": "chrony_time_sync|CHRONY_NOT_SYNCHRONIZED",
      "description": "System clock is not synchronized with NTP sources via chronyd, which can cause certificate validation failures and log timestamp drift.",
      "category": { "name": "Stability" },
      "total_risk": 3,
      "risk_of_change": 1,
      "impact": { "name": "Time Drift", "impact": 3 },
      "likelihood": 3,
      "hosts_acked_count": 0,
      "impacted_systems_count": 9,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-05-10T00:00:00Z"
    },
    {
      "rule_id": "kdump_service_check|KDUMP_NOT_RUNNING",
      "description": "The kdump crash recovery service is not active, meaning kernel crash dumps will not be captured for root cause analysis.",
      "category": { "name": "Stability" },
      "total_risk": 3,
      "risk_of_change": 1,
      "impact": { "name": "Crash Analysis Loss", "impact": 3 },
      "likelihood": 2,
      "hosts_acked_count": 1,
      "impacted_systems_count": 11,
      "playbook_count": 1,
      "reboot_required": false,
      "publish_date": "2025-04-25T00:00:00Z"
    }
  ]
}
```

## 3. User-Facing Response

Your environment has **62 active advisor recommendations** across your systems. Here's the breakdown by category:

- **Security:** 19 recommendations
- **Stability:** 18 recommendations
- **Availability:** 14 recommendations
- **Performance:** 11 recommendations

### Top Recommendations (Highest Risk)

#### Critical Risk (Total Risk: 4)

| Recommendation | Category | Affected Systems | Remediation Playbook |
|---|---|---|---|
| Bonding configuration uses improperly quoted options, which may cause network interface failover to malfunction | Availability | 23 | Yes |
| SSH service allows weak cryptographic ciphers, increasing risk of unauthorized access | Security | 18 | Yes |
| Kernel `panic_on_warn` is enabled, causing unnecessary reboots on non-fatal warnings | Stability | 15 (reboot required) | Yes |

#### Important Risk (Total Risk: 3)

| Recommendation | Category | Affected Systems | Remediation Playbook |
|---|---|---|---|
| Active tuned profile does not match the recommended profile for system workload | Performance | 31 | Yes |
| DNF/YUM repositories have GPG signature verification disabled | Security | 14 | Yes |
| System clock not synchronized via chronyd — may cause cert validation failures | Stability | 9 | Yes |
| kdump crash recovery service is not active — crash dumps will not be captured | Stability | 11 | Yes |

The 3 critical-risk recommendations should be prioritized — in particular, the **weak SSH ciphers** issue affects 18 systems and poses a direct security risk, and the **bonding configuration** issue affects 23 systems and could cause network failover failures.

All of the top recommendations have Ansible remediation playbooks available. Note that this agent operates in read-only mode — to apply remediations, use your standard change management process or run the playbooks through Ansible Automation Platform.

Showing 7 of 62 total recommendations. Would you like me to focus on a specific category (Security, Stability, Availability, or Performance), show which systems are affected by a particular recommendation, or continue with the next set of results?

---

## Skill Adherence Analysis

| Skill | How It Influenced the Response |
|---|---|
| **tool-invocation-rules** | Used proper JSON argument types (`limit` as integer `20`, `sort` as string `"-total_risk"`). Did not generate pseudocode or Python — made actual tool calls. Omitted optional arguments that weren't needed. |
| **multi-step-workflows** | Followed the multi-step pattern: first `advisor__get_recommendations_stats` for the overview, then `advisor__get_active_rules` for detailed rules. Did not stop at a single tool call — chained calls to build a complete answer. |
| **efficient-counting** | Read `meta.count` from the rules response to know the total (62) without paginating. Used the stats endpoint totals for the category breakdown. |
| **response-formatting** | Grouped recommendations by severity (Critical Risk / Important Risk). Included rule description and number of affected systems per the skill directive. Capped at 20 items with a "would you like more" offer. Led with a brief summary paragraph before the detailed sections. Did not open with a self-introduction. |
| **guardrails-safety** | Applied partial data transparency: "Showing 7 of 62 total recommendations." Proactively noted read-only mode when mentioning remediation playbooks, redirecting to change management. Did not fabricate comparative data or benchmarks. |
| **error-handling** | No errors occurred, so no recovery was needed. Would have retried with reduced limit or added filters if `tool_result_too_large` had been returned. |
