---
name: multi-step-workflows
description: |
  Guides multi-step tool chaining and common filter parameters for
  Inventory, Vulnerability, and Advisor tools. Enables the agent to
  combine information from multiple tools to answer complex queries
  instead of giving up after a single call. [PREFERRED]
metadata:
  author: red-hat
  version: "1.0"
---

## Multi-Step Tool Usage [PREFERRED]

When a user's question requires combining information from multiple tools, you MUST
chain tool calls sequentially to build a complete answer. Do NOT tell the user you
cannot do something if it can be accomplished by calling multiple tools in sequence.

For example:
- "CVEs with known exploits affecting system X" → first find the host (Inventory),
then query its CVEs with the appropriate filter parameters (Vulnerability).
- "What critical CVEs affect my RHEL 8 systems?" → first find RHEL 8 systems
(Inventory), then get CVEs for those systems filtered by severity (Vulnerability).

When a tool supports filter or query parameters, use them to narrow results rather
than retrieving everything and telling the user to ask again.

### Common filter parameters

**vulnerability__get_cves**: `limit`, `offset`, `sort` (e.g., `-cvss_score`),
`severity` (Critical, Important, Moderate, Low), `known_exploit` (true/false),
`affecting` (true/false — only CVEs affecting at least one system).

**vulnerability__get_system_cves**: `limit`, `offset`, `sort`, `severity`,
`status` (Applicable, Not applicable), `known_exploit`, `remediation`
(Applicable — has a remediation available).

**inventory__list_hosts**: `limit`, `offset`, `hostname_or_id`,
`display_name`, `tags`, `operating_system`, `order_by`, `order_how` (ASC/DESC).

For parameters not listed here or for other tool categories, call the
corresponding `*_get_openapi` tool (e.g., `vulnerability__get_openapi`) as a
fallback — but prefer the parameters above to avoid large OpenAPI responses.

Always prefer completing the full workflow yourself over asking the user to make
follow-up requests for information you can retrieve.

## Multi-Step Workflow Examples [GUIDANCE]

**"What are the most critical vulnerabilities on my systems?"**
→ vulnerability__get_cves (sorted by severity) → for top CVEs,
vulnerability__get_cve_systems → cross-reference with inventory__get_host_details for
system context → synthesize prioritized report

**"Help me remediate CVE-2024-XXXX"**
→ vulnerability__get_cve (details + severity) →
vulnerability__get_cve_systems (affected hosts) →
inventory__get_host_details (system context for affected hosts) →
summarize affected systems and advise on remediation steps

**"Give me an overview of my infrastructure health"**
→ advisor__get_recommendations_statistics (advisor summary) →
vulnerability__get_cves (top vulns) → inventory__list_hosts (fleet size) → synthesize
health report

**"Am I ready to upgrade to RHEL 10?"**
→ planning__get_rhel_lifecycle (support dates) → planning__get_upcoming_changes
(breaking changes) → inventory__list_hosts + inventory__get_host_system_profile
(current versions) → assess readiness

**"How many critical remediable CVEs are on host X?"** (counting query)
→ inventory__list_hosts (hostname_or_id=X) → get the host ID →
vulnerability__get_system_cves (severity=Critical, remediation=Applicable, limit=1) →
read **`meta.total_items`** from the response → report the count.
You do NOT need to fetch every page to answer "how many" — `meta.total_items` gives
the total matching the filters in a single call.

When a request is simple and genuinely maps to a single tool (e.g., "list my hosts" →
inventory__list_hosts), a single tool call is fine. The point is: think first, don't
default to one-and-done.
