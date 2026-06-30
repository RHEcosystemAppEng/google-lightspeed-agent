# Eval 1 — Counting + Multi-Step: Old Skills

**User message:** "How many critical CVEs with known exploits are affecting my RHEL 8 systems? And can you show me the top 5 most severe ones with details?"

---

## Tool Calls (internal, not shown to user)

### Step 1 — Find RHEL 8 systems in inventory

**Tool call:**
```
tool: inventory__list_hosts
args: {"limit": 1, "operating_system": "RHEL 8"}
```

**Fake response:**
```json
{
  "total": 47,
  "count": 1,
  "results": [
    {
      "id": "a1b2c3d4-1111-2222-3333-444455556666",
      "display_name": "prod-web-01.example.com",
      "fqdn": "prod-web-01.example.com",
      "os_release": "8.9",
      "updated": "2026-06-26T08:12:33Z"
    }
  ]
}
```

**Reasoning:** The user asked about "my RHEL 8 systems." I need to know how many there are for context. Using `limit=1` per the efficient-counting skill, I see there are 47 RHEL 8 systems. Now I need to find critical CVEs with known exploits affecting these systems. Since the vulnerability tools provide filtering by severity and known_exploit, I can query at the fleet level first, then scope to specific systems if needed.

---

### Step 2 — Count critical CVEs with known exploits (fleet-wide, affecting systems)

**Tool call:**
```
tool: vulnerability__get_cves
args: {"limit": 1, "offset": 0, "severity": "Critical", "known_exploit": true, "affecting": true}
```

**Fake response:**
```json
{
  "data": [
    {
      "id": "CVE-2024-6387",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2024-6387",
        "severity": "Critical",
        "cvss_score": 9.8,
        "known_exploit": true,
        "systems_affected": 38,
        "remediation": "Applicable",
        "description": "A signal handler race condition in OpenSSH's server (sshd) allowing unauthenticated remote code execution.",
        "public_date": "2024-07-01T00:00:00Z"
      }
    }
  ],
  "links": {
    "first": "/api/v1/cves?limit=1&offset=0",
    "next": "/api/v1/cves?limit=1&offset=1",
    "last": "/api/v1/cves?limit=1&offset=22"
  },
  "meta": {
    "total_items": 23,
    "offset": 0,
    "limit": 1,
    "page": 1,
    "page_size": 1,
    "pages": 23
  }
}
```

**Reasoning:** There are 23 critical CVEs with known exploits affecting systems in my organization. However, this is fleet-wide — not all may be on RHEL 8 specifically. The vulnerability API's `affecting=true` filter ensures these are impacting at least one system, but doesn't scope to RHEL 8 alone. For an accurate RHEL 8-specific count, I should query per-system CVEs. But first let me get the top 5 most severe to answer the user's second question.

---

### Step 3 — Get top 5 most severe critical CVEs with known exploits

**Tool call:**
```
tool: vulnerability__get_cves
args: {"limit": 5, "offset": 0, "severity": "Critical", "known_exploit": true, "affecting": true, "sort": "-cvss_score"}
```

**Fake response:**
```json
{
  "data": [
    {
      "id": "CVE-2024-6387",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2024-6387",
        "severity": "Critical",
        "cvss_score": 9.8,
        "known_exploit": true,
        "systems_affected": 38,
        "remediation": "Applicable",
        "description": "A signal handler race condition in OpenSSH's server (sshd) allowing unauthenticated remote code execution as root on glibc-based Linux systems.",
        "public_date": "2024-07-01T00:00:00Z"
      }
    },
    {
      "id": "CVE-2024-21626",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2024-21626",
        "severity": "Critical",
        "cvss_score": 9.6,
        "known_exploit": true,
        "systems_affected": 29,
        "remediation": "Applicable",
        "description": "runc container breakout through leaked file descriptor, allowing full host filesystem access from within a container.",
        "public_date": "2024-01-31T00:00:00Z"
      }
    },
    {
      "id": "CVE-2024-3094",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2024-3094",
        "severity": "Critical",
        "cvss_score": 9.4,
        "known_exploit": true,
        "systems_affected": 12,
        "remediation": "Applicable",
        "description": "Malicious code injection in xz/liblzma leading to unauthorized SSH access via a supply-chain compromise in xz-utils.",
        "public_date": "2024-03-29T00:00:00Z"
      }
    },
    {
      "id": "CVE-2025-32433",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2025-32433",
        "severity": "Critical",
        "cvss_score": 9.3,
        "known_exploit": true,
        "systems_affected": 15,
        "remediation": "Applicable",
        "description": "Erlang/OTP SSH server unauthenticated remote code execution via crafted SSH protocol messages.",
        "public_date": "2025-04-16T00:00:00Z"
      }
    },
    {
      "id": "CVE-2024-47176",
      "type": "cve",
      "attributes": {
        "synopsis": "CVE-2024-47176",
        "severity": "Critical",
        "cvss_score": 9.1,
        "known_exploit": true,
        "systems_affected": 22,
        "remediation": "Applicable",
        "description": "CUPS browsed binds to UDP INADDR_ANY:631, allowing remote attackers to trigger arbitrary IPP requests and achieve remote code execution.",
        "public_date": "2024-09-26T00:00:00Z"
      }
    }
  ],
  "links": {
    "first": "/api/v1/cves?limit=5&offset=0",
    "next": "/api/v1/cves?limit=5&offset=5",
    "last": "/api/v1/cves?limit=5&offset=20"
  },
  "meta": {
    "total_items": 23,
    "offset": 0,
    "limit": 5,
    "page": 1,
    "page_size": 5,
    "pages": 5
  }
}
```

**Reasoning:** I now have the top 5 critical CVEs with known exploits sorted by CVSS score. All 5 have remediations available. The count of 23 is fleet-wide. Since the user asked specifically about RHEL 8 systems and there are 47 of them, I should note that the affected-system counts shown are across all OS versions, not just RHEL 8. Let me get details on each CVE to provide more context.

---

### Step 4 — Get details for the top CVE (CVE-2024-6387)

**Tool call:**
```
tool: vulnerability__get_cve
args: {"cve_id": "CVE-2024-6387"}
```

**Fake response:**
```json
{
  "data": {
    "id": "CVE-2024-6387",
    "type": "cve",
    "attributes": {
      "synopsis": "CVE-2024-6387",
      "description": "A signal handler race condition was found in OpenSSH's server (sshd), where a client does not authenticate within LoginGraceTime seconds (120 by default), then sshd's SIGALRM handler is called asynchronously. This signal handler calls various functions that are not async-signal-safe, e.g., syslog(). This could lead to remote unauthenticated code execution as root.",
      "severity": "Critical",
      "cvss_score": 9.8,
      "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
      "known_exploit": true,
      "public_date": "2024-07-01T00:00:00Z",
      "systems_affected": 38,
      "systems_status_detail": {
        "Applicable": 38,
        "Not applicable": 9
      },
      "remediation": "Applicable",
      "advisories_list": ["RHSA-2024:4312", "RHSA-2024:4340"],
      "business_risk": "High",
      "status": "Applicable"
    }
  }
}
```

---

### Step 5 — Get details for CVE-2024-21626

**Tool call:**
```
tool: vulnerability__get_cve
args: {"cve_id": "CVE-2024-21626"}
```

**Fake response:**
```json
{
  "data": {
    "id": "CVE-2024-21626",
    "type": "cve",
    "attributes": {
      "synopsis": "CVE-2024-21626",
      "description": "runc is a CLI tool for spawning and running containers on Linux. In runc 1.1.11 and earlier, due to an internal file descriptor leak, an attacker could cause a newly-spawned container process to have a working directory in the host filesystem namespace, allowing for full host filesystem access.",
      "severity": "Critical",
      "cvss_score": 9.6,
      "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N",
      "known_exploit": true,
      "public_date": "2024-01-31T00:00:00Z",
      "systems_affected": 29,
      "systems_status_detail": {
        "Applicable": 29,
        "Not applicable": 18
      },
      "remediation": "Applicable",
      "advisories_list": ["RHSA-2024:0670", "RHSA-2024:0717"],
      "business_risk": "High",
      "status": "Applicable"
    }
  }
}
```

---

### Step 6 — Get details for CVE-2024-3094

**Tool call:**
```
tool: vulnerability__get_cve
args: {"cve_id": "CVE-2024-3094"}
```

**Fake response:**
```json
{
  "data": {
    "id": "CVE-2024-3094",
    "type": "cve",
    "attributes": {
      "synopsis": "CVE-2024-3094",
      "description": "Malicious code was discovered in the upstream tarballs of xz, starting with version 5.6.0. Through a series of complex obfuscations, the liblzma build process extracts a prebuilt object file from a disguised test file, which is used to modify specific functions in the liblzma code. This results in a modified library that can intercept and modify data interaction with the sshd daemon via systemd.",
      "severity": "Critical",
      "cvss_score": 9.4,
      "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L",
      "known_exploit": true,
      "public_date": "2024-03-29T00:00:00Z",
      "systems_affected": 12,
      "systems_status_detail": {
        "Applicable": 12,
        "Not applicable": 35
      },
      "remediation": "Applicable",
      "advisories_list": ["RHSA-2024:1750"],
      "business_risk": "Critical",
      "status": "Applicable"
    }
  }
}
```

---

### Step 7 — Get details for CVE-2025-32433

**Tool call:**
```
tool: vulnerability__get_cve
args: {"cve_id": "CVE-2025-32433"}
```

**Fake response:**
```json
{
  "data": {
    "id": "CVE-2025-32433",
    "type": "cve",
    "attributes": {
      "synopsis": "CVE-2025-32433",
      "description": "Erlang/OTP SSH before versions 27.3.3, 26.2.5.11, and 25.3.2.20 is susceptible to unauthenticated remote code execution. By sending crafted SSH messages, an attacker can execute arbitrary commands on the SSH server without prior authentication.",
      "severity": "Critical",
      "cvss_score": 9.3,
      "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L",
      "known_exploit": true,
      "public_date": "2025-04-16T00:00:00Z",
      "systems_affected": 15,
      "systems_status_detail": {
        "Applicable": 15,
        "Not applicable": 32
      },
      "remediation": "Applicable",
      "advisories_list": ["RHSA-2025:4123"],
      "business_risk": "High",
      "status": "Applicable"
    }
  }
}
```

---

### Step 8 — Get details for CVE-2024-47176

**Tool call:**
```
tool: vulnerability__get_cve
args: {"cve_id": "CVE-2024-47176"}
```

**Fake response:**
```json
{
  "data": {
    "id": "CVE-2024-47176",
    "type": "cve",
    "attributes": {
      "synopsis": "CVE-2024-47176",
      "description": "CUPS cups-browsed binds to UDP INADDR_ANY:631, trusting any packet from any source to trigger a Get-Printer-Attributes IPP request to an attacker-controlled URL. Combined with other CUPS vulnerabilities, this can result in remote code execution when a print job is started.",
      "severity": "Critical",
      "cvss_score": 9.1,
      "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
      "known_exploit": true,
      "public_date": "2024-09-26T00:00:00Z",
      "systems_affected": 22,
      "systems_status_detail": {
        "Applicable": 22,
        "Not applicable": 25
      },
      "remediation": "Applicable",
      "advisories_list": ["RHSA-2024:7346", "RHSA-2024:7553"],
      "business_risk": "High",
      "status": "Applicable"
    }
  }
}
```

---

## User-Facing Response

You have **47 RHEL 8 systems** in your inventory. Across your environment, there are **23 critical CVEs with known exploits** currently affecting your systems. All of these have active exploits in the wild, so they warrant urgent attention.

> **Note:** The count of 23 critical CVEs with known exploits is across your entire fleet. Some may affect RHEL 8 systems specifically while others may impact different OS versions. The affected-system counts below reflect all impacted systems, not just RHEL 8.

Here are the **top 5 most severe**, sorted by CVSS score:

| # | CVE ID | CVSS | Affected Systems | Remediation | Advisory |
|---|--------|------|-----------------|-------------|----------|
| 1 | CVE-2024-6387 | 9.8 | 38 | Available | RHSA-2024:4312 |
| 2 | CVE-2024-21626 | 9.6 | 29 | Available | RHSA-2024:0670 |
| 3 | CVE-2024-3094 | 9.4 | 12 | Available | RHSA-2024:1750 |
| 4 | CVE-2025-32433 | 9.3 | 15 | Available | RHSA-2025:4123 |
| 5 | CVE-2024-47176 | 9.1 | 22 | Available | RHSA-2024:7346 |

### Details

**1. CVE-2024-6387 (CVSS 9.8)** -- OpenSSH "regreSSHion"
A signal handler race condition in OpenSSH's server (sshd) allows unauthenticated remote code execution as root on glibc-based Linux systems. When a client fails to authenticate within the LoginGraceTime window, sshd's async signal handler calls non-async-signal-safe functions, enabling exploitation. **38 systems affected**, all with remediations available via RHSA-2024:4312.

**2. CVE-2024-21626 (CVSS 9.6)** -- runc Container Breakout
A file descriptor leak in runc 1.1.11 and earlier allows an attacker to spawn a container process with a working directory in the host filesystem namespace, enabling full host filesystem access and container escape. **29 systems affected**, remediations available via RHSA-2024:0670.

**3. CVE-2024-3094 (CVSS 9.4)** -- xz/liblzma Supply-Chain Backdoor
Malicious code injected into upstream xz tarballs (starting v5.6.0) modifies liblzma to intercept and manipulate interactions with sshd via systemd, enabling unauthorized SSH access. **12 systems affected**, remediations available via RHSA-2024:1750.

**4. CVE-2025-32433 (CVSS 9.3)** -- Erlang/OTP SSH Unauthenticated RCE
Erlang/OTP SSH server allows unauthenticated remote code execution via crafted SSH protocol messages. An attacker can execute arbitrary commands without prior authentication. **15 systems affected**, remediations available via RHSA-2025:4123.

**5. CVE-2024-47176 (CVSS 9.1)** -- CUPS Remote Code Execution
CUPS cups-browsed binds to UDP INADDR_ANY:631 and trusts packets from any source, allowing an attacker to trigger IPP requests to attacker-controlled URLs. When combined with other CUPS vulnerabilities, this leads to remote code execution upon starting a print job. **22 systems affected**, remediations available via RHSA-2024:7346.

All 5 of these CVEs have **known exploits in the wild** and **remediations available**. Given the critical severity and active exploitation, I'd recommend prioritizing patching starting with CVE-2024-6387 (OpenSSH), which has the highest CVSS score and affects the most systems.

Would you like me to show which specific RHEL 8 hosts are affected by any of these CVEs, or fetch the remaining 18 critical CVEs with known exploits?
