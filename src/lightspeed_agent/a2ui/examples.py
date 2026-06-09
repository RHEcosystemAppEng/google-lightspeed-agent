"""Domain-specific A2UI v0.8 examples for Red Hat Insights data.

These examples teach the LLM how to format Insights responses using
A2UI Basic Catalog v0.8 components. Each example is a complete, valid
A2UI payload with surfaceUpdate, dataModelUpdate, and beginRendering.
"""

INSIGHTS_A2UI_EXAMPLES = """
## Red Hat Insights A2UI Examples

Use these examples as templates when rendering Red Hat Insights data.
Each shows the correct A2UI v0.8 flat adjacency-list structure with
surfaceUpdate, dataModelUpdate, and beginRendering.

### Example 1: CVE Vulnerability Table

Use this pattern when displaying lists of CVEs from the Vulnerability service.
Columns: CVE ID, Severity, CVSS Score, Affected Systems, Status.

```json
{
  "a2ui": [
    {
      "surfaceUpdate": {
        "components": [
          {
            "column": {
              "id": "vuln_root",
              "children": {
                "explicitList": ["vuln_title", "vuln_table"]
              }
            }
          },
          {
            "text": {
              "id": "vuln_title",
              "text": "Critical & Important Vulnerabilities",
              "style": "headline"
            }
          },
          {
            "table": {
              "id": "vuln_table",
              "columns": [
                {"header": "CVE ID", "field": "cve_id"},
                {"header": "Severity", "field": "severity"},
                {"header": "CVSS Score", "field": "cvss_score"},
                {"header": "Affected Systems", "field": "affected_systems"},
                {"header": "Status", "field": "status"}
              ]
            }
          }
        ]
      }
    },
    {
      "dataModelUpdate": {
        "data": {
          "vuln_table": {
            "rows": [
              {
                "cve_id": "CVE-2024-1234",
                "severity": "Critical",
                "cvss_score": "9.8",
                "affected_systems": "12",
                "status": "Applicable"
              },
              {
                "cve_id": "CVE-2024-5678",
                "severity": "Important",
                "cvss_score": "7.5",
                "affected_systems": "8",
                "status": "Applicable"
              }
            ]
          }
        }
      }
    },
    {
      "beginRendering": {}
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
      "surfaceUpdate": {
        "components": [
          {
            "card": {
              "id": "rec_card",
              "child": "rec_content"
            }
          },
          {
            "column": {
              "id": "rec_content",
              "children": {
                "explicitList": [
                  "rec_title",
                  "rec_risk_row",
                  "rec_desc",
                  "rec_remediation_title",
                  "rec_remediation_text",
                  "rec_action_btn"
                ]
              }
            }
          },
          {
            "text": {
              "id": "rec_title",
              "text": "Recommendation: Update OpenSSL packages",
              "style": "headline"
            }
          },
          {
            "row": {
              "id": "rec_risk_row",
              "children": {
                "explicitList": ["rec_risk_label", "rec_systems_label"]
              }
            }
          },
          {
            "text": {
              "id": "rec_risk_label",
              "text": "Risk: Critical"
            }
          },
          {
            "text": {
              "id": "rec_systems_label",
              "text": "Affected Systems: 15"
            }
          },
          {
            "text": {
              "id": "rec_desc",
              "text": "OpenSSL < 3.0.13 is vulnerable to CVE-2024-0727. Update to fix."
            }
          },
          {
            "text": {
              "id": "rec_remediation_title",
              "text": "Remediation Steps",
              "style": "subheadline"
            }
          },
          {
            "text": {
              "id": "rec_remediation_text",
              "text": "1. Review affected systems\\n2. Create playbook\\n3. Execute"
            }
          },
          {
            "button": {
              "id": "rec_action_btn",
              "child": "rec_action_btn_text"
            }
          },
          {
            "text": {
              "id": "rec_action_btn_text",
              "text": "Create Remediation Playbook"
            }
          }
        ]
      }
    },
    {
      "dataModelUpdate": {
        "data": {}
      }
    },
    {
      "beginRendering": {}
    }
  ]
}
```

### Example 3: System Inventory Table

Use this pattern when listing registered systems from the Inventory service.
Columns: Display Name, OS, Last Check-in, Stale Status.

```json
{
  "a2ui": [
    {
      "surfaceUpdate": {
        "components": [
          {
            "column": {
              "id": "inv_root",
              "children": {
                "explicitList": ["inv_title", "inv_summary", "inv_table"]
              }
            }
          },
          {
            "text": {
              "id": "inv_title",
              "text": "Registered Systems",
              "style": "headline"
            }
          },
          {
            "text": {
              "id": "inv_summary",
              "text": "Showing 3 of 142 systems"
            }
          },
          {
            "table": {
              "id": "inv_table",
              "columns": [
                {"header": "Display Name", "field": "display_name"},
                {"header": "Operating System", "field": "os"},
                {"header": "Last Check-in", "field": "last_seen"},
                {"header": "Status", "field": "stale_status"}
              ]
            }
          }
        ]
      }
    },
    {
      "dataModelUpdate": {
        "data": {
          "inv_table": {
            "rows": [
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
    },
    {
      "beginRendering": {}
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
      "surfaceUpdate": {
        "components": [
          {
            "card": {
              "id": "remed_card",
              "child": "remed_content"
            }
          },
          {
            "column": {
              "id": "remed_content",
              "children": {
                "explicitList": [
                  "remed_title",
                  "remed_info_row",
                  "remed_systems_title",
                  "remed_systems_table",
                  "remed_execute_btn"
                ]
              }
            }
          },
          {
            "text": {
              "id": "remed_title",
              "text": "Remediation Playbook: Fix OpenSSL CVEs",
              "style": "headline"
            }
          },
          {
            "row": {
              "id": "remed_info_row",
              "children": {
                "explicitList": ["remed_created", "remed_actions_count"]
              }
            }
          },
          {
            "text": {
              "id": "remed_created",
              "text": "Created: 2024-12-01"
            }
          },
          {
            "text": {
              "id": "remed_actions_count",
              "text": "Actions: 3"
            }
          },
          {
            "text": {
              "id": "remed_systems_title",
              "text": "Systems Covered",
              "style": "subheadline"
            }
          },
          {
            "table": {
              "id": "remed_systems_table",
              "columns": [
                {"header": "System", "field": "system_name"},
                {"header": "Issue", "field": "issue"},
                {"header": "Action", "field": "action"}
              ]
            }
          },
          {
            "button": {
              "id": "remed_execute_btn",
              "child": "remed_execute_btn_text"
            }
          },
          {
            "text": {
              "id": "remed_execute_btn_text",
              "text": "Execute Playbook"
            }
          }
        ]
      }
    },
    {
      "dataModelUpdate": {
        "data": {
          "remed_systems_table": {
            "rows": [
              {
                "system_name": "prod-web-01.example.com",
                "issue": "CVE-2024-1234",
                "action": "Update openssl to 3.0.13"
              },
              {
                "system_name": "prod-web-02.example.com",
                "issue": "CVE-2024-1234",
                "action": "Update openssl to 3.0.13"
              },
              {
                "system_name": "db-primary.example.com",
                "issue": "CVE-2024-5678",
                "action": "Update kernel to 5.14.0-362.24.1"
              }
            ]
          }
        }
      }
    },
    {
      "beginRendering": {}
    }
  ]
}
```
"""
