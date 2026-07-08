"""Domain-specific A2UI v0.9 examples for Red Hat Insights data.

These examples teach the LLM how to format Insights responses using
A2UI Basic Catalog v0.9 components. Each example is a complete, valid
A2UI payload with createSurface, updateComponents, and updateDataModel.
"""

INSIGHTS_A2UI_EXAMPLES = """
## Red Hat Insights A2UI Examples

Use these examples as templates when rendering Red Hat Insights data.
Each shows the correct A2UI v0.9 flat component structure with
createSurface, updateComponents, and updateDataModel.

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

### Example 3: System Inventory List

Use this pattern when listing registered systems from the Inventory service.
Each system is rendered as a Card showing display name, OS, last check-in,
and stale status. Uses data binding to populate values from the data model.

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
            "id": "inv_root",
            "children": ["inv_title", "inv_summary", "inv_list"]
          },
          {
            "component": "Text",
            "id": "inv_title",
            "text": "Registered Systems",
            "usageHint": "h1"
          },
          {
            "component": "Text",
            "id": "inv_summary",
            "text": {"$data": "/summary"}
          },
          {
            "component": "List",
            "id": "inv_list",
            "children": ["inv_card_1", "inv_card_2", "inv_card_3"]
          },
          {
            "component": "Card",
            "id": "inv_card_1",
            "children": ["inv_col_1"]
          },
          {
            "component": "Column",
            "id": "inv_col_1",
            "children": ["inv_1_name", "inv_1_details"]
          },
          {
            "component": "Text",
            "id": "inv_1_name",
            "text": {"$data": "/systems/0/display_name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "inv_1_details",
            "children": ["inv_1_os", "inv_1_checkin", "inv_1_status"]
          },
          {
            "component": "Text",
            "id": "inv_1_os",
            "text": {"$data": "/systems/0/os"}
          },
          {
            "component": "Text",
            "id": "inv_1_checkin",
            "text": {"$data": "/systems/0/last_seen"}
          },
          {
            "component": "Text",
            "id": "inv_1_status",
            "text": {"$data": "/systems/0/stale_status"}
          },
          {
            "component": "Card",
            "id": "inv_card_2",
            "children": ["inv_col_2"]
          },
          {
            "component": "Column",
            "id": "inv_col_2",
            "children": ["inv_2_name", "inv_2_details"]
          },
          {
            "component": "Text",
            "id": "inv_2_name",
            "text": {"$data": "/systems/1/display_name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "inv_2_details",
            "children": ["inv_2_os", "inv_2_checkin", "inv_2_status"]
          },
          {
            "component": "Text",
            "id": "inv_2_os",
            "text": {"$data": "/systems/1/os"}
          },
          {
            "component": "Text",
            "id": "inv_2_checkin",
            "text": {"$data": "/systems/1/last_seen"}
          },
          {
            "component": "Text",
            "id": "inv_2_status",
            "text": {"$data": "/systems/1/stale_status"}
          },
          {
            "component": "Card",
            "id": "inv_card_3",
            "children": ["inv_col_3"]
          },
          {
            "component": "Column",
            "id": "inv_col_3",
            "children": ["inv_3_name", "inv_3_details"]
          },
          {
            "component": "Text",
            "id": "inv_3_name",
            "text": {"$data": "/systems/2/display_name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "inv_3_details",
            "children": ["inv_3_os", "inv_3_checkin", "inv_3_status"]
          },
          {
            "component": "Text",
            "id": "inv_3_os",
            "text": {"$data": "/systems/2/os"}
          },
          {
            "component": "Text",
            "id": "inv_3_checkin",
            "text": {"$data": "/systems/2/last_seen"}
          },
          {
            "component": "Text",
            "id": "inv_3_status",
            "text": {"$data": "/systems/2/stale_status"}
          }
        ]
      }
    },
    {
      "version": "v0.9",
      "updateDataModel": {
        "surfaceId": "main",
        "value": {
          "summary": "Showing 3 of 142 systems",
          "systems": [
            {
              "display_name": "prod-web-01.example.com",
              "os": "RHEL 9.4",
              "last_seen": "2024-12-01T10:30:00Z",
              "stale_status": "Fresh"
            },
            {
              "display_name": "db-primary.example.com",
              "os": "RHEL 8.10",
              "last_seen": "2024-11-30T22:15:00Z",
              "stale_status": "Fresh"
            },
            {
              "display_name": "legacy-app.example.com",
              "os": "RHEL 7.9",
              "last_seen": "2024-11-15T08:00:00Z",
              "stale_status": "Stale"
            }
          ]
        }
      }
    }
  ]
}
```

### Example 4: Remediation Summary Card

Use this pattern when showing a remediation playbook summary with the systems
it covers and an action button to execute.

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
            "id": "remed_card",
            "children": ["remed_content"]
          },
          {
            "component": "Column",
            "id": "remed_content",
            "children": [
              "remed_title",
              "remed_info_row",
              "remed_systems_title",
              "remed_systems_list",
              "remed_execute_btn"
            ]
          },
          {
            "component": "Text",
            "id": "remed_title",
            "text": "Remediation Playbook: Fix OpenSSL CVEs",
            "usageHint": "h1"
          },
          {
            "component": "Row",
            "id": "remed_info_row",
            "children": ["remed_created", "remed_actions_count"]
          },
          {
            "component": "Text",
            "id": "remed_created",
            "text": "Created: 2024-12-01"
          },
          {
            "component": "Text",
            "id": "remed_actions_count",
            "text": "Actions: 3"
          },
          {
            "component": "Text",
            "id": "remed_systems_title",
            "text": "Systems Covered",
            "usageHint": "h2"
          },
          {
            "component": "List",
            "id": "remed_systems_list",
            "children": ["remed_sys_card_1", "remed_sys_card_2", "remed_sys_card_3"]
          },
          {
            "component": "Card",
            "id": "remed_sys_card_1",
            "children": ["remed_sys_row_1"]
          },
          {
            "component": "Row",
            "id": "remed_sys_row_1",
            "children": ["remed_sys_1_name", "remed_sys_1_issue", "remed_sys_1_action"]
          },
          {
            "component": "Text",
            "id": "remed_sys_1_name",
            "text": "prod-web-01.example.com"
          },
          {
            "component": "Text",
            "id": "remed_sys_1_issue",
            "text": "CVE-2024-1234"
          },
          {
            "component": "Text",
            "id": "remed_sys_1_action",
            "text": "Update openssl to 3.0.13"
          },
          {
            "component": "Card",
            "id": "remed_sys_card_2",
            "children": ["remed_sys_row_2"]
          },
          {
            "component": "Row",
            "id": "remed_sys_row_2",
            "children": ["remed_sys_2_name", "remed_sys_2_issue", "remed_sys_2_action"]
          },
          {
            "component": "Text",
            "id": "remed_sys_2_name",
            "text": "prod-web-02.example.com"
          },
          {
            "component": "Text",
            "id": "remed_sys_2_issue",
            "text": "CVE-2024-1234"
          },
          {
            "component": "Text",
            "id": "remed_sys_2_action",
            "text": "Update openssl to 3.0.13"
          },
          {
            "component": "Card",
            "id": "remed_sys_card_3",
            "children": ["remed_sys_row_3"]
          },
          {
            "component": "Row",
            "id": "remed_sys_row_3",
            "children": ["remed_sys_3_name", "remed_sys_3_issue", "remed_sys_3_action"]
          },
          {
            "component": "Text",
            "id": "remed_sys_3_name",
            "text": "db-primary.example.com"
          },
          {
            "component": "Text",
            "id": "remed_sys_3_issue",
            "text": "CVE-2024-5678"
          },
          {
            "component": "Text",
            "id": "remed_sys_3_action",
            "text": "Update kernel to 5.14.0-362.24.1"
          },
          {
            "component": "Button",
            "id": "remed_execute_btn",
            "children": ["remed_execute_btn_text"]
          },
          {
            "component": "Text",
            "id": "remed_execute_btn_text",
            "text": "Execute Playbook"
          }
        ]
      }
    }
  ]
}
```

### Example 5: RHEL Lifecycle & Upcoming Changes

Use this pattern when showing RHEL version lifecycle dates or upcoming changes
from the Planning service. Each lifecycle entry is a Card with version, phase,
and key dates. Uses data binding to populate values from the data model.

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
            "id": "plan_root",
            "children": ["plan_title", "plan_summary", "plan_list"]
          },
          {
            "component": "Text",
            "id": "plan_title",
            "text": "RHEL Lifecycle Overview",
            "usageHint": "h1"
          },
          {
            "component": "Text",
            "id": "plan_summary",
            "text": {"$data": "/summary"}
          },
          {
            "component": "List",
            "id": "plan_list",
            "children": ["plan_card_1", "plan_card_2", "plan_card_3"]
          },
          {
            "component": "Card",
            "id": "plan_card_1",
            "children": ["plan_col_1"]
          },
          {
            "component": "Column",
            "id": "plan_col_1",
            "children": ["plan_1_version", "plan_1_dates", "plan_1_status"]
          },
          {
            "component": "Text",
            "id": "plan_1_version",
            "text": {"$data": "/versions/0/name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "plan_1_dates",
            "children": ["plan_1_ga", "plan_1_eus", "plan_1_eol"]
          },
          {
            "component": "Text",
            "id": "plan_1_ga",
            "text": {"$data": "/versions/0/ga_date"}
          },
          {
            "component": "Text",
            "id": "plan_1_eus",
            "text": {"$data": "/versions/0/eus_end"}
          },
          {
            "component": "Text",
            "id": "plan_1_eol",
            "text": {"$data": "/versions/0/eol_date"}
          },
          {
            "component": "Text",
            "id": "plan_1_status",
            "text": {"$data": "/versions/0/phase"}
          },
          {
            "component": "Card",
            "id": "plan_card_2",
            "children": ["plan_col_2"]
          },
          {
            "component": "Column",
            "id": "plan_col_2",
            "children": ["plan_2_version", "plan_2_dates", "plan_2_status"]
          },
          {
            "component": "Text",
            "id": "plan_2_version",
            "text": {"$data": "/versions/1/name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "plan_2_dates",
            "children": ["plan_2_ga", "plan_2_eus", "plan_2_eol"]
          },
          {
            "component": "Text",
            "id": "plan_2_ga",
            "text": {"$data": "/versions/1/ga_date"}
          },
          {
            "component": "Text",
            "id": "plan_2_eus",
            "text": {"$data": "/versions/1/eus_end"}
          },
          {
            "component": "Text",
            "id": "plan_2_eol",
            "text": {"$data": "/versions/1/eol_date"}
          },
          {
            "component": "Text",
            "id": "plan_2_status",
            "text": {"$data": "/versions/1/phase"}
          },
          {
            "component": "Card",
            "id": "plan_card_3",
            "children": ["plan_col_3"]
          },
          {
            "component": "Column",
            "id": "plan_col_3",
            "children": ["plan_3_version", "plan_3_dates", "plan_3_status"]
          },
          {
            "component": "Text",
            "id": "plan_3_version",
            "text": {"$data": "/versions/2/name"},
            "usageHint": "h2"
          },
          {
            "component": "Row",
            "id": "plan_3_dates",
            "children": ["plan_3_ga", "plan_3_eus", "plan_3_eol"]
          },
          {
            "component": "Text",
            "id": "plan_3_ga",
            "text": {"$data": "/versions/2/ga_date"}
          },
          {
            "component": "Text",
            "id": "plan_3_eus",
            "text": {"$data": "/versions/2/eus_end"}
          },
          {
            "component": "Text",
            "id": "plan_3_eol",
            "text": {"$data": "/versions/2/eol_date"}
          },
          {
            "component": "Text",
            "id": "plan_3_status",
            "text": {"$data": "/versions/2/phase"}
          }
        ]
      }
    },
    {
      "version": "v0.9",
      "updateDataModel": {
        "surfaceId": "main",
        "value": {
          "summary": "RHEL lifecycle status for your deployed versions",
          "versions": [
            {
              "name": "RHEL 9",
              "ga_date": "GA: 2022-05-18",
              "eus_end": "EUS ends: 2027-05-31",
              "eol_date": "EOL: 2032-05-31",
              "phase": "Phase: Full Support"
            },
            {
              "name": "RHEL 8",
              "ga_date": "GA: 2019-05-07",
              "eus_end": "EUS ends: 2024-05-31",
              "eol_date": "EOL: 2029-05-31",
              "phase": "Phase: Maintenance Support"
            },
            {
              "name": "RHEL 7",
              "ga_date": "GA: 2014-06-10",
              "eus_end": "EUS ended: 2021-08-30",
              "eol_date": "EOL: 2024-06-30",
              "phase": "Phase: End of Life"
            }
          ]
        }
      }
    }
  ]
}
```
"""
