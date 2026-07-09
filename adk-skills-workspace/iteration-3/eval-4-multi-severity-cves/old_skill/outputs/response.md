# Eval 4: "Show me the top critical and important CVEs affecting my systems."

## 1. Activated Skills

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Need correct parameter names and types for `vulnerability__get_cves` — specifically `severity`, `affecting`, `sort`, and `limit` |
| **multi-step-workflows** | User asks for CVEs "affecting my systems" — maps to the workflow: `vulnerability__get_cves` (sorted by severity) then present synthesized results. Two severity values requested (Critical + Important), requiring two separate calls since `severity` accepts a single value |
| **response-formatting** | CVE list output — must use table format with CVE ID, Severity, Affected Systems, Remediation Available columns, sorted by severity descending |
| **guardrails-safety** | CVE severity interpretation — emphasize urgency for Critical/Important CVEs, note known exploits for extra emphasis |
| **efficient-counting** | Not directly activated (user wants to *see* CVEs, not count them), but the `meta.total_items` field is used to report pagination context |
| **error-handling** | Standing readiness — would activate if any call returns oversized results or errors |

## 2. Tool Calls

### Step 1a: Fetch Critical CVEs affecting the user's systems

```
tool: vulnerability__get_cves
args: {
  "severity": "Critical",
  "affecting": true,
  "sort": "-cvss_score",
  "limit": 20
}
```

**Simulated Response:**
```json
{
  "data": [
    {
      "id": "CVE-2024-6387",
      "attributes": {
        "synopsis": "OpenSSH Remote Code Execution (regresshion)",
        "severity": "Critical",
        "cvss_score": 8.1,
        "public_date": "2024-07-01",
        "systems_affected": 47,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-47076",
      "attributes": {
        "synopsis": "cups-filters - Remote Code Execution via IPP",
        "severity": "Critical",
        "cvss_score": 8.6,
        "public_date": "2024-09-26",
        "systems_affected": 12,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-21626",
      "attributes": {
        "synopsis": "runc container breakout via leaked file descriptor",
        "severity": "Critical",
        "cvss_score": 8.6,
        "public_date": "2024-01-31",
        "systems_affected": 31,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2023-38545",
      "attributes": {
        "synopsis": "curl SOCKS5 heap buffer overflow",
        "severity": "Critical",
        "cvss_score": 7.5,
        "public_date": "2023-10-11",
        "systems_affected": 8,
        "remediation_available": true,
        "known_exploit": false
      }
    }
  ],
  "meta": {
    "total_items": 4,
    "limit": 20,
    "offset": 0
  }
}
```

### Step 1b: Fetch Important CVEs affecting the user's systems (parallel with 1a)

```
tool: vulnerability__get_cves
args: {
  "severity": "Important",
  "affecting": true,
  "sort": "-cvss_score",
  "limit": 20
}
```

**Simulated Response:**
```json
{
  "data": [
    {
      "id": "CVE-2024-3596",
      "attributes": {
        "synopsis": "RADIUS protocol forgery via MD5 collision (BlastRADIUS)",
        "severity": "Important",
        "cvss_score": 9.0,
        "public_date": "2024-07-09",
        "systems_affected": 19,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-1086",
      "attributes": {
        "synopsis": "kernel nf_tables use-after-free privilege escalation",
        "severity": "Important",
        "cvss_score": 7.8,
        "public_date": "2024-01-31",
        "systems_affected": 54,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-6409",
      "attributes": {
        "synopsis": "OpenSSH signal handler race condition",
        "severity": "Important",
        "cvss_score": 7.0,
        "public_date": "2024-07-08",
        "systems_affected": 47,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-2961",
      "attributes": {
        "synopsis": "glibc iconv buffer overflow",
        "severity": "Important",
        "cvss_score": 7.3,
        "public_date": "2024-04-17",
        "systems_affected": 38,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2023-46846",
      "attributes": {
        "synopsis": "Squid HTTP request smuggling",
        "severity": "Important",
        "cvss_score": 7.2,
        "public_date": "2023-10-19",
        "systems_affected": 5,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-38473",
      "attributes": {
        "synopsis": "httpd mod_proxy encoding problem",
        "severity": "Important",
        "cvss_score": 6.5,
        "public_date": "2024-07-01",
        "systems_affected": 22,
        "remediation_available": true,
        "known_exploit": false
      }
    }
  ],
  "meta": {
    "total_items": 63,
    "limit": 20,
    "offset": 0
  }
}
```

## 3. User-Facing Response

You have **4 Critical** and **63 Important** CVEs currently affecting your systems. Here are the top ones, prioritized by CVSS score:

### Critical CVEs

| CVE ID | Synopsis | CVSS | Affected Systems | Remediation | Known Exploit |
|---|---|---|---|---|---|
| CVE-2024-47076 | cups-filters - Remote Code Execution via IPP | 8.6 | 12 | Yes | No |
| CVE-2024-21626 | runc container breakout via leaked file descriptor | 8.6 | 31 | Yes | **Yes** |
| CVE-2024-6387 | OpenSSH Remote Code Execution (regresshion) | 8.1 | 47 | Yes | **Yes** |
| CVE-2023-38545 | curl SOCKS5 heap buffer overflow | 7.5 | 8 | Yes | No |

### Important CVEs (showing top 6 of 63)

| CVE ID | Synopsis | CVSS | Affected Systems | Remediation | Known Exploit |
|---|---|---|---|---|---|
| CVE-2024-3596 | RADIUS protocol forgery (BlastRADIUS) | 9.0 | 19 | Yes | No |
| CVE-2024-1086 | kernel nf_tables use-after-free privilege escalation | 7.8 | 54 | Yes | **Yes** |
| CVE-2024-2961 | glibc iconv buffer overflow | 7.3 | 38 | Yes | No |
| CVE-2023-46846 | Squid HTTP request smuggling | 7.2 | 5 | Yes | No |
| CVE-2024-6409 | OpenSSH signal handler race condition | 7.0 | 47 | Yes | No |
| CVE-2024-38473 | httpd mod_proxy encoding problem | 6.5 | 22 | Yes | No |

...and 57 more Important CVEs. Ask me to continue or apply filters to narrow down.

**Immediate attention recommended:** Three CVEs have known exploits in the wild:
- **CVE-2024-6387** (Critical) and **CVE-2024-21626** (Critical) both have confirmed exploits and affect 47 and 31 systems respectively. Remediations are available for both.
- **CVE-2024-1086** (Important) has a known exploit and affects the largest number of systems (54). Despite being Important rather than Critical, the active exploitation warrants prioritizing this alongside the Critical CVEs.

All listed CVEs have remediations available. Would you like me to show the affected systems for any of these, or help you plan remediation?

---

## Behavioral Notes

**Skills interaction observed:**
- **tool-invocation-rules**: The `severity` parameter accepts a single value, so two separate calls were needed for Critical and Important. The `affecting=true` parameter correctly filtered to only CVEs affecting at least one of the user's systems.
- **multi-step-workflows**: The workflow example suggests following up with `vulnerability__get_cve_systems` and `inventory__get_host_details` for a full picture, but the agent appropriately stopped after Step 1 since the user asked to "show" CVEs, not to see affected system details. The agent offered follow-up instead of over-fetching.
- **response-formatting**: CVE table format used with required columns. Results sorted by severity (Critical first) then CVSS descending. The Important section was capped at the fetched 6 (of 63 total) with a continuation prompt, following the "cap at 20 items" guidance.
- **guardrails-safety**: Known exploit CVEs were highlighted with extra emphasis per the severity interpretation rules. The agent noted that CVE-2024-1086 (Important with known exploit) may warrant faster action than some CVEs with higher severity but no exploit — directly applying the "known exploits deserve extra emphasis regardless of severity label" guidance.
- **efficient-counting**: `meta.total_items` was used to report the total count of Important CVEs (63) without needing additional calls.
- **error-handling**: No errors encountered; skill was on standby.
