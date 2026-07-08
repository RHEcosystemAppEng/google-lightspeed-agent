---
name: multi-step-workflows
description: |
  Answering complex questions that require combining multiple tools or
  chaining calls across Inventory, Vulnerability, and Advisor APIs. Use
  this skill when a user question cannot be answered with a single tool
  call — e.g. correlating hosts with CVEs, filtering advisories by
  system, or joining data across Red Hat Insights services. [PREFERRED]
metadata:
  author: red-hat
  version: "1.1"
---

## Multi-Step Tool Usage

When a user's question requires combining information from multiple tools, chain
tool calls sequentially to build a complete answer. Do not tell the user you cannot
do something if it can be accomplished by calling multiple tools in sequence.

For example:
- "CVEs with known exploits affecting system X" -> find the host (Inventory),
  then query its CVEs with the appropriate filter parameters (Vulnerability).
- "What critical CVEs affect my RHEL 8 systems?" -> find RHEL 8 systems
  (Inventory), then get CVEs for those systems filtered by severity (Vulnerability).

When a tool supports filter or query parameters, use them to narrow results rather
than retrieving everything and telling the user to ask again.

### Tool disambiguation: system/host listing

Two tools list systems — they query different services and return different counts:

| Tool | Service | Scope |
|---|---|---|
| `inventory__list_hosts` | Inventory | All registered systems (including immutable/edge) |
| `vulnerability__get_systems` | Vulnerability | Only systems tracked for CVE analysis (excludes immutable) |

**Selection rule:**
- General "how many systems/hosts?" or "list my systems" ->
  `inventory__list_hosts` (source of truth for the full fleet).
- "Which systems are affected by CVE-X?" or vulnerability-scoped queries ->
  `vulnerability__get_systems` or `vulnerability__get_cve_systems`.
- When the user says "inventory", always use `inventory__list_hosts`.

Always prefer completing the full workflow yourself over asking the user to make
follow-up requests for information you can retrieve.

## Workflow Examples

**"What are the most critical vulnerabilities on my systems?"**
-> `vulnerability__get_cves` (sorted by severity) -> for top CVEs,
`vulnerability__get_cve_systems` -> cross-reference with `inventory__get_host_details`
for system context -> synthesize prioritized report

**"Help me remediate CVE-2024-XXXX"**
-> `vulnerability__get_cve` (details + severity) ->
`vulnerability__get_cve_systems` (affected hosts) ->
`inventory__get_host_details` (system context) ->
summarize affected systems and advise on remediation steps

**"Give me an overview of my infrastructure health"**
-> `advisor__get_recommendations_stats` (advisor summary) ->
`vulnerability__get_cves` (top vulns) -> `inventory__list_hosts` (fleet size) ->
synthesize health report

**"Am I ready to upgrade to RHEL 10?"**
-> `planning__get_rhel_lifecycle` (support dates) -> `planning__get_upcoming_changes`
(breaking changes) -> `inventory__list_hosts` + `inventory__get_host_system_profile`
(current versions) -> assess readiness

When a request genuinely maps to a single tool (e.g., "list my hosts" ->
`inventory__list_hosts`), a single call is fine. The point is: think first, don't
default to one-and-done.
