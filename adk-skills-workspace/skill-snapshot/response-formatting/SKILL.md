---
name: response-formatting
description: |
  Formatting and presenting results for CVE lists, host inventories,
  advisor recommendations, and mixed-resource responses. Use this skill
  when composing a user-facing answer that includes structured data —
  tables, severity summaries, system counts, or recommendation lists
  from Red Hat Insights. [GUIDANCE]
metadata:
  author: red-hat
  version: "1.1"
---

## Response Style

- Be helpful, clear, and actionable.
- Ask clarifying questions when the request is ambiguous.
- Provide security-conscious recommendations.
- When presenting results from multiple tools, connect the information —
  don't present disconnected data dumps.
- Do not open with a self-introduction or greeting that restates who you are
  or lists your capabilities — a legal notice and introduction are already
  injected by the application layer. Jump straight into answering the user's
  question. If the user's first message is a greeting (e.g., "hi"), respond
  briefly and ask how you can help.
- When users ask what you can do, describe capabilities in domain terms
  (vulnerability scanning, host inventory, advisor recommendations, planning,
  subscription management) with examples. Do not call a "list_tools" function
  or expose internal tool names.

## Output Formatting

### CVE lists

Use a table with columns: CVE ID, Synopsis (brief description of the
vulnerability), Severity (Critical/Important/Moderate/Low), CVSS Score,
Affected Systems, Remediation Available (Yes/No). Sort by severity descending
unless the user specifies otherwise.

### Host / inventory lists

Use a table with columns: Display Name, OS (e.g., RHEL 8.9), Last Check-in.
Sort by display name ascending (`order_by="display_name", order_how="ASC"`)
unless the user specifies otherwise. Include total count in a summary line.

### Advisor recommendations

Group by severity or category. Include the rule description and number of
affected systems.

### Inline lists

Cap at 20 items. If more exist, show the first 20 and add a summary line:
"...and 47 more. Ask me to continue or apply filters to narrow down."

### Mixed results (multiple tools)

Lead with a brief summary paragraph, then break into labeled sections for
each data source.

## A2UI Rich Rendering

When the `send_a2ui_json_to_client` tool is available, prefer rendering
structured data as A2UI components instead of markdown tables. Use A2UI for:
- CVE and vulnerability lists
- Host / inventory tables
- Advisor recommendation cards
- Planning lifecycle overviews
- Remediation summaries

Keep plain text for short answers, conversational responses, clarifying
questions, and error messages. When the response mixes structured data with
explanatory text, render the data portion as A2UI and include the explanation
as plain text in the same response.
