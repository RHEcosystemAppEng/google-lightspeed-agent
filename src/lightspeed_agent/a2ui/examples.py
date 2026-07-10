"""Domain-specific A2UI v0.9 examples for Red Hat Insights data.

These examples teach the LLM how to format Insights responses using
A2UI Basic Catalog v0.9 components. Each example is a complete, valid
A2UI payload with createSurface and updateComponents.

Only two examples are included to keep the system prompt compact — the model
generalises the pattern to other Insights domains (inventory, planning,
remediations) without additional examples.
"""

INSIGHTS_A2UI_EXAMPLES = """
## Red Hat Insights A2UI Examples

Use these examples as templates when rendering Red Hat Insights data.
Each shows the correct A2UI v0.9 flat component structure with
createSurface and updateComponents. Adapt the same pattern for other
Insights data (inventory lists, planning lifecycle, remediations).

### Example 1: CVE Vulnerability List

Use this pattern when displaying lists of CVEs from the Vulnerability service.
Each CVE is rendered as a Card within a List, showing ID, severity, CVSS score,
affected systems, and status.

```json
{
  "a2ui": [
    {
      "version": "v0.9",
      "createSurface": {
        "surfaceId": "main",
        "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
      }
    },
    {
      "version": "v0.9",
      "updateComponents": {
        "surfaceId": "main",
        "components": [
          {
            "component": "Column",
            "id": "vuln_root",
            "children": ["vuln_title", "vuln_list"]
          },
          {
            "component": "Text",
            "id": "vuln_title",
            "text": "Critical & Important Vulnerabilities",
            "usageHint": "h1"
          },
          {
            "component": "List",
            "id": "vuln_list",
            "children": ["vuln_card_1", "vuln_card_2"]
          },
          {
            "component": "Card",
            "id": "vuln_card_1",
            "children": ["vuln_col_1"]
          },
          {
            "component": "Column",
            "id": "vuln_col_1",
            "children": ["vuln_1_id", "vuln_1_details"]
          },
          {
            "component": "Text",
            "id": "vuln_1_id",
            "text": "CVE-2024-1234",
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "vuln_1_details",
            "children": ["vuln_1_severity", "vuln_1_cvss", "vuln_1_systems", "vuln_1_status"]
          },
          {
            "component": "Text",
            "id": "vuln_1_severity",
            "text": "Severity: Critical"
          },
          {
            "component": "Text",
            "id": "vuln_1_cvss",
            "text": "CVSS: 9.8"
          },
          {
            "component": "Text",
            "id": "vuln_1_systems",
            "text": "Affected: 12 systems"
          },
          {
            "component": "Text",
            "id": "vuln_1_status",
            "text": "Status: Applicable"
          },
          {
            "component": "Card",
            "id": "vuln_card_2",
            "children": ["vuln_col_2"]
          },
          {
            "component": "Column",
            "id": "vuln_col_2",
            "children": ["vuln_2_id", "vuln_2_details"]
          },
          {
            "component": "Text",
            "id": "vuln_2_id",
            "text": "CVE-2024-5678",
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "vuln_2_details",
            "children": ["vuln_2_severity", "vuln_2_cvss", "vuln_2_systems", "vuln_2_status"]
          },
          {
            "component": "Text",
            "id": "vuln_2_severity",
            "text": "Severity: Important"
          },
          {
            "component": "Text",
            "id": "vuln_2_cvss",
            "text": "CVSS: 7.5"
          },
          {
            "component": "Text",
            "id": "vuln_2_systems",
            "text": "Affected: 8 systems"
          },
          {
            "component": "Text",
            "id": "vuln_2_status",
            "text": "Status: Applicable"
          }
        ]
      }
    }
  ]
}
```

### Example 2: Advisor Recommendation Card

Use this pattern when showing a single Advisor recommendation with risk level,
description, affected systems count, and remediation guidance.

```json
{
  "a2ui": [
    {
      "version": "v0.9",
      "createSurface": {
        "surfaceId": "main",
        "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
      }
    },
    {
      "version": "v0.9",
      "updateComponents": {
        "surfaceId": "main",
        "components": [
          {
            "component": "Card",
            "id": "rec_card",
            "children": ["rec_content"]
          },
          {
            "component": "Column",
            "id": "rec_content",
            "children": [
              "rec_title",
              "rec_risk_row",
              "rec_desc",
              "rec_remediation_title",
              "rec_remediation_text",
              "rec_action_btn"
            ]
          },
          {
            "component": "Text",
            "id": "rec_title",
            "text": "Recommendation: Update OpenSSL packages",
            "usageHint": "h1"
          },
          {
            "component": "Row",
            "id": "rec_risk_row",
            "children": ["rec_risk_label", "rec_systems_label"]
          },
          {
            "component": "Text",
            "id": "rec_risk_label",
            "text": "Risk: Critical"
          },
          {
            "component": "Text",
            "id": "rec_systems_label",
            "text": "Affected Systems: 15"
          },
          {
            "component": "Text",
            "id": "rec_desc",
            "text": "OpenSSL < 3.0.13 is vulnerable to CVE-2024-0727. Update to fix."
          },
          {
            "component": "Text",
            "id": "rec_remediation_title",
            "text": "Remediation Steps",
            "usageHint": "h2"
          },
          {
            "component": "Text",
            "id": "rec_remediation_text",
            "text": "1. Review affected systems\\n2. Create playbook\\n3. Execute"
          },
          {
            "component": "Button",
            "id": "rec_action_btn",
            "children": ["rec_action_btn_text"]
          },
          {
            "component": "Text",
            "id": "rec_action_btn_text",
            "text": "Create Remediation Playbook"
          }
        ]
      }
    }
  ]
}
```

"""
