# Eval 4 — "Show me the top critical and important CVEs affecting my systems." (With Skills)

## 1. Skills Activated

| Skill | Reason |
|---|---|
| **tool-invocation-rules** | Provides correct `impact` parameter encoding — numeric IDs `"3,4"` for Important+Critical in a single call |
| **multi-step-workflows** | Query is landscape-level (no specific system named) so routes to `vulnerability__get_cves`; recommends `advisory_available="true"` and CVSS sort |
| **response-formatting** | CVE list requires table format with CVE ID, Synopsis, Severity, CVSS Score, Affected Systems, Remediation Available columns |
| **guardrails-safety** | Severity interpretation guidance, partial-data transparency ("Showing N of M") |
| **efficient-counting** | Not directly triggered (user asked for "top" CVEs, not a count), but the `meta.total_items` field is used for transparency |

## 2. Tool Calls

### Call 1: Get top Critical and Important CVEs

**Reasoning**: The user wants "top critical and important CVEs." Per **multi-step-workflows**, no specific system is named, so this is a landscape-level query routed to `vulnerability__get_cves`. Per **tool-invocation-rules**, the `impact` parameter uses comma-separated numeric IDs: `"4"` = Critical, `"3"` = Important, combined as `"3,4"`. Adding `sort="-cvss_score"` surfaces the most severe first, and `advisory_available="true"` restricts to actionable CVEs with available advisories.

```
tool: vulnerability__get_cves
args: {
  "impact": "3,4",
  "sort": "-cvss_score",
  "advisory_available": "true",
  "limit": 20
}
```

**Simulated Response**:
```json
{
  "meta": {
    "total_items": 87,
    "limit": 20,
    "offset": 0
  },
  "data": [
    {
      "id": "CVE-2024-6387",
      "synopsis": "Race condition in OpenSSH server (regreSSHion)",
      "severity": "Critical",
      "impact": "Critical",
      "cvss_score": 9.8,
      "systems_affected": 42,
      "known_exploit": true,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-21626",
      "synopsis": "Container breakout via runc file descriptor leak",
      "severity": "Critical",
      "impact": "Critical",
      "cvss_score": 9.6,
      "systems_affected": 18,
      "known_exploit": true,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-3094",
      "synopsis": "Supply chain compromise in xz/liblzma (backdoor)",
      "severity": "Critical",
      "impact": "Critical",
      "cvss_score": 9.4,
      "systems_affected": 5,
      "known_exploit": true,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-47076",
      "synopsis": "Remote code execution via CUPS browsed service",
      "severity": "Critical",
      "impact": "Critical",
      "cvss_score": 9.1,
      "systems_affected": 31,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-38816",
      "synopsis": "Spring Framework path traversal via WebMvc.fn",
      "severity": "Critical",
      "impact": "Critical",
      "cvss_score": 9.0,
      "systems_affected": 7,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-9341",
      "synopsis": "Privilege escalation in container runtime mount handling",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 8.6,
      "systems_affected": 22,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-45490",
      "synopsis": "Heap buffer overflow in libexpat XML parser",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 8.4,
      "systems_affected": 38,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-50602",
      "synopsis": "Denial of service in libxml2 via crafted XML input",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 8.2,
      "systems_affected": 45,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-45769",
      "synopsis": "Heap corruption in PCP performance monitoring",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 8.1,
      "systems_affected": 12,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-28182",
      "synopsis": "HTTP/2 CONTINUATION flood in nghttp2 library",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.9,
      "systems_affected": 29,
      "known_exploit": true,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-5953",
      "synopsis": "Denial of service in 389 Directory Server BER encoding",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.7,
      "systems_affected": 8,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-45770",
      "synopsis": "Symlink race condition in PCP pmpost utility",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.5,
      "systems_affected": 12,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-6345",
      "synopsis": "Remote code execution via Python setuptools URL handling",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.4,
      "systems_affected": 15,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-8088",
      "synopsis": "Infinite loop in Python zipfile when processing crafted archives",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.3,
      "systems_affected": 20,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-6232",
      "synopsis": "ReDoS vulnerability in Python tarfile header parsing",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.2,
      "systems_affected": 20,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-4032",
      "synopsis": "Incorrect IP address categorization in Python ipaddress module",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.1,
      "systems_affected": 20,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-52530",
      "synopsis": "HTTP request smuggling in libsoup via header parsing",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.0,
      "systems_affected": 33,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-52532",
      "synopsis": "Infinite loop in libsoup WebSocket handling",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 7.0,
      "systems_affected": 33,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-11168",
      "synopsis": "URL validation bypass in Python urllib.parse",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 6.9,
      "systems_affected": 20,
      "known_exploit": false,
      "advisory_available": true
    },
    {
      "id": "CVE-2024-9676",
      "synopsis": "Symlink traversal vulnerability in Podman and Buildah",
      "severity": "Important",
      "impact": "Important",
      "cvss_score": 6.8,
      "systems_affected": 14,
      "known_exploit": false,
      "advisory_available": true
    }
  ]
}
```

## 3. User-Facing Response

Here are the top Critical and Important CVEs affecting your systems, sorted by CVSS score. Showing 20 of 87 total CVEs with advisories available.

### Critical CVEs

| CVE ID | Synopsis | CVSS | Affected Systems | Known Exploit | Remediation |
|---|---|---|---|---|---|
| CVE-2024-6387 | Race condition in OpenSSH server (regreSSHion) | 9.8 | 42 | **Yes** | Available |
| CVE-2024-21626 | Container breakout via runc file descriptor leak | 9.6 | 18 | **Yes** | Available |
| CVE-2024-3094 | Supply chain compromise in xz/liblzma (backdoor) | 9.4 | 5 | **Yes** | Available |
| CVE-2024-47076 | Remote code execution via CUPS browsed service | 9.1 | 31 | No | Available |
| CVE-2024-38816 | Spring Framework path traversal via WebMvc.fn | 9.0 | 7 | No | Available |

### Important CVEs

| CVE ID | Synopsis | CVSS | Affected Systems | Known Exploit | Remediation |
|---|---|---|---|---|---|
| CVE-2024-9341 | Privilege escalation in container runtime mount handling | 8.6 | 22 | No | Available |
| CVE-2024-45490 | Heap buffer overflow in libexpat XML parser | 8.4 | 38 | No | Available |
| CVE-2024-50602 | Denial of service in libxml2 via crafted XML input | 8.2 | 45 | No | Available |
| CVE-2024-45769 | Heap corruption in PCP performance monitoring | 8.1 | 12 | No | Available |
| CVE-2024-28182 | HTTP/2 CONTINUATION flood in nghttp2 library | 7.9 | 29 | **Yes** | Available |
| CVE-2024-5953 | Denial of service in 389 Directory Server BER encoding | 7.7 | 8 | No | Available |
| CVE-2024-45770 | Symlink race condition in PCP pmpost utility | 7.5 | 12 | No | Available |
| CVE-2024-6345 | Remote code execution via Python setuptools URL handling | 7.4 | 15 | No | Available |
| CVE-2024-8088 | Infinite loop in Python zipfile when processing crafted archives | 7.3 | 20 | No | Available |
| CVE-2024-6232 | ReDoS vulnerability in Python tarfile header parsing | 7.2 | 20 | No | Available |
| CVE-2024-4032 | Incorrect IP address categorization in Python ipaddress module | 7.1 | 20 | No | Available |
| CVE-2024-52530 | HTTP request smuggling in libsoup via header parsing | 7.0 | 33 | No | Available |
| CVE-2024-52532 | Infinite loop in libsoup WebSocket handling | 7.0 | 33 | No | Available |
| CVE-2024-11168 | URL validation bypass in Python urllib.parse | 6.9 | 20 | No | Available |
| CVE-2024-9676 | Symlink traversal vulnerability in Podman and Buildah | 6.8 | 14 | No | Available |

**Key findings:**

- **4 CVEs have known exploits** in the wild (CVE-2024-6387, CVE-2024-21626, CVE-2024-3094, and CVE-2024-28182) — these warrant priority attention regardless of the number of affected systems.
- **CVE-2024-6387 (regreSSHion)** is the highest-priority item: CVSS 9.8 with a known exploit affecting 42 systems. This OpenSSH race condition allows unauthenticated remote code execution.
- **CVE-2024-50602** affects the most systems (45) among the Important-severity CVEs.
- All 20 CVEs shown have advisories available with remediation steps.

There are 67 more Important and Critical CVEs beyond this list. Would you like me to show more, drill into a specific CVE for affected systems and remediation details, or focus on CVEs with known exploits?

---

## Skill Evaluation Notes

### Correct behaviors demonstrated (with skills):

1. **Single API call for multi-severity query**: Used `impact="3,4"` (comma-separated numeric IDs) to fetch both Critical and Important CVEs in one call, as documented in tool-invocation-rules under "Multi-impact queries." Without the skill, an agent might make two separate calls or use wrong string values like `"Critical,Important"`.

2. **Correct parameter names and types**: Used `impact` (not `severity`), numeric string IDs `"3,4"` (not label names), `sort="-cvss_score"` (not `sort_by` or `order`), and `advisory_available="true"` (string, not boolean). All per tool-invocation-rules confirmed parameters.

3. **Correct tool selection**: Chose `vulnerability__get_cves` (global landscape query) over `vulnerability__get_system_cves` (per-system). Per multi-step-workflows: "No specific system named -> `vulnerability__get_cves`."

4. **Actionable filtering with `advisory_available="true"`**: Per multi-step-workflows workflow example, restricts to CVEs where remediation is available — making results immediately actionable.

5. **Table format split by severity**: Per response-formatting, used the CVE table schema (CVE ID, Synopsis, Severity, CVSS Score, Affected Systems, Remediation Available) and sorted by severity descending. Split into Critical and Important sections for clarity.

6. **Known-exploit emphasis**: Per guardrails-safety, CVEs with known exploits received bold emphasis and a dedicated callout in the key findings, noting that "a Moderate CVE with a known exploit may warrant faster action."

7. **Partial-data transparency**: Per guardrails-safety and response-formatting, stated "Showing 20 of 87 total CVEs" and offered to show more or narrow down — not silently truncating.

8. **Offer to drill deeper**: Proactively offered follow-up options (more CVEs, specific CVE details, known-exploit focus) per multi-step-workflows principle of completing the workflow rather than leaving the user to figure out next steps.
