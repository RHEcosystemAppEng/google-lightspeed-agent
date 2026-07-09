# Eval 4 — Multi-Severity CVEs (Old/Snapshot Skills)

**User Query:** "Show me the top critical and important CVEs affecting my systems."

---

## 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Multi-severity query guidance — `severity` accepts only one value; use `sort=-cvss_score` strategy |
| **multi-step-workflows** | Landscape-level CVE query with no specific system named — maps to `vulnerability__get_cves` with `affecting=true` |
| **response-formatting** | CVE list output — table format with severity, affected systems, remediation columns |
| **guardrails-safety** | Severity interpretation, partial-data transparency |

---

## 2. Tool Calls

### Step 1: Fetch top CVEs sorted by CVSS score (covers both Critical and Important)

The snapshot skill `tool-invocation-rules` says for multi-severity queries: "Preferred — sort by score: Omit `severity` and use `sort=-cvss_score`. The top results will naturally be Critical and Important."

The snapshot skill `multi-step-workflows` confirms: use `vulnerability__get_cves` with `sort=-cvss_score, affecting=true, limit=20`.

```
tool: vulnerability__get_cves
args: {
  "limit": 20,
  "sort": "-cvss_score",
  "affecting": true
}
```

**Simulated Response:**
```json
{
  "data": [
    {
      "id": "CVE-2024-6387",
      "attributes": {
        "synopsis": "OpenSSH regreSSHion RCE",
        "severity": "Critical",
        "cvss_score": 9.8,
        "systems_affected": 42,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-21626",
      "attributes": {
        "synopsis": "runc container breakout via leaked file descriptors",
        "severity": "Critical",
        "cvss_score": 9.6,
        "systems_affected": 18,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-3094",
      "attributes": {
        "synopsis": "xz/liblzma backdoor (supply chain compromise)",
        "severity": "Critical",
        "cvss_score": 9.4,
        "systems_affected": 7,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-1086",
      "attributes": {
        "synopsis": "Linux kernel nf_tables use-after-free privilege escalation",
        "severity": "Important",
        "cvss_score": 8.8,
        "systems_affected": 31,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-27198",
      "attributes": {
        "synopsis": "JetBrains TeamCity authentication bypass",
        "severity": "Important",
        "cvss_score": 8.5,
        "systems_affected": 3,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-4577",
      "attributes": {
        "synopsis": "PHP CGI argument injection RCE",
        "severity": "Important",
        "cvss_score": 8.1,
        "systems_affected": 12,
        "remediation_available": true,
        "known_exploit": true
      }
    },
    {
      "id": "CVE-2024-38063",
      "attributes": {
        "synopsis": "Linux kernel TCP/IP stack integer underflow",
        "severity": "Important",
        "cvss_score": 7.8,
        "systems_affected": 25,
        "remediation_available": false,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-5535",
      "attributes": {
        "synopsis": "OpenSSL SSL_select_next_proto buffer overread",
        "severity": "Important",
        "cvss_score": 7.5,
        "systems_affected": 38,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-2961",
      "attributes": {
        "synopsis": "glibc iconv buffer overflow",
        "severity": "Important",
        "cvss_score": 7.4,
        "systems_affected": 15,
        "remediation_available": true,
        "known_exploit": false
      }
    },
    {
      "id": "CVE-2024-32002",
      "attributes": {
        "synopsis": "Git recursive clone RCE via symlinks",
        "severity": "Important",
        "cvss_score": 7.2,
        "systems_affected": 9,
        "remediation_available": true,
        "known_exploit": false
      }
    }
  ],
  "meta": {
    "total_items": 87,
    "limit": 20,
    "offset": 0
  }
}
```

**Note:** The snapshot skills use the parameter name `affecting` (boolean). This may not match the actual MCP schema parameter name, which could be different (e.g., `affected`, `affects_systems`, etc.). The snapshot skills document this as a confirmed parameter but it may be incorrect.

---

## 3. User-Facing Response

Here are the top critical and important CVEs currently affecting your systems, sorted by CVSS score:

| CVE ID | Severity | CVSS | Affected Systems | Known Exploit | Remediation Available |
|---|---|---|---|---|---|
| CVE-2024-6387 | Critical | 9.8 | 42 | Yes | Yes |
| CVE-2024-21626 | Critical | 9.6 | 18 | Yes | Yes |
| CVE-2024-3094 | Critical | 9.4 | 7 | Yes | Yes |
| CVE-2024-1086 | Important | 8.8 | 31 | Yes | Yes |
| CVE-2024-27198 | Important | 8.5 | 3 | No | Yes |
| CVE-2024-4577 | Important | 8.1 | 12 | Yes | Yes |
| CVE-2024-38063 | Important | 7.8 | 25 | No | No |
| CVE-2024-5535 | Important | 7.5 | 38 | No | Yes |
| CVE-2024-2961 | Important | 7.4 | 15 | No | Yes |
| CVE-2024-32002 | Important | 7.2 | 9 | No | Yes |

Showing 10 of 87 total CVEs affecting your systems.

**Key findings:**
- **3 Critical CVEs** all have known exploits and remediations available — these should be prioritized immediately.
- **CVE-2024-6387** (OpenSSH regreSSHion) has the widest blast radius at 42 affected systems with a known exploit.
- **CVE-2024-1086** (kernel privilege escalation) affects 31 systems and also has a known exploit.
- **CVE-2024-38063** is the only Important CVE without a remediation available yet — monitor this one for updates.

Would you like me to drill into any specific CVE to see which systems are affected, or focus on the ones with known exploits?

---

## 4. Analysis — Potential Issues with Snapshot Skills

1. **Parameter name correctness**: The snapshot skills list `affecting` as a confirmed parameter for `vulnerability__get_cves`. If the actual MCP schema uses a different parameter name (e.g., `affected`, `affects_system`, or `filter[affecting]`), this call would either fail or the parameter would be silently ignored — returning CVEs that do NOT affect any of the user's systems, polluting results.

2. **Sort parameter format**: The snapshot skills document `sort` with a value of `"-cvss_score"` (dash prefix for descending). If the actual API uses a different sort syntax (e.g., `"-public_date"`, separate `sort_by` + `sort_order` parameters, or `"cvss_score:desc"`), the sort would fail or be ignored.

3. **Single tool call approach**: The snapshot skills recommend the "sort by score" strategy as preferred over separate calls per severity. This works if the API returns a mix of severities sorted by score, but the user specifically asked for "critical AND important" — the sort approach might return Moderate CVEs with high CVSS scores alongside the Critical/Important ones, which wouldn't strictly match the user's request.

4. **No `known_exploit` filter used**: The snapshot skills don't suggest proactively filtering by `known_exploit=true` for this query, though they note in guardrails that known-exploit CVEs deserve extra emphasis. The response does highlight known exploits in the output, but doesn't offer to filter by them upfront.
