---
name: jira-mcp
description: >-
  Use a self-hosted Jira Server or Data Center account to search, read, create,
  update, comment on, assign, or transition issues through the bundled Jira MCP.
  Use when the user mentions Jira issue keys, assigned issues, creating Jira,
  editing fields, comments, assignees, or workflow status.
---

# Jira MCP

Use the configured Jira MCP for standard Jira operations. The bundled server supports Jira Server and Data Center 8.x, including installations that require Basic Auth because Personal Access Tokens are unavailable.

## Tool workflow

- Verify the active identity with `jira_whoami` before the first write or whenever identity is uncertain.
- Search with `jira_search_issues`. For the current user's assigned work, prefer `assignee = currentUser() ORDER BY updated DESC`.
- Read an issue with `jira_get_issue` and retain its real Jira URL.
- Create with `jira_get_create_fields` → `jira_prepare_issue` → user approval → `jira_create_issue`.
- Update fields with `jira_get_edit_fields` → user approval → `jira_update_issue`.
- Change status with `jira_get_transitions` → user approval → `jira_transition_issue`.
- Add comments with `jira_add_comment` and change assignees with `jira_assign_issue` after showing the exact change.
- Verify every write from the returned Jira readback. A failed item does not prove that other items succeeded.

Do not guess custom field IDs, accepted values, issue types, or transitions. Query live metadata first. The server intentionally does not provide deletion or attachment tools.

## Identity and credentials

Each person must configure their own Jira identity. Stop before writing if `jira_whoami` returns another user.

Never print, copy, save, or commit a real password or token. On macOS, use the bundled setup so the password is entered invisibly and stored in that person's Keychain. Do not distribute another person's Codex configuration, environment files, or Keychain data.

## Missing MCP setup

If the Jira MCP is unavailable, do not fall back to browser automation. When the user asks to install and configure it, read [references/setup.md](references/setup.md) and complete the bundled setup in the same task. The explicit installation request is sufficient approval for the documented local setup; do not stop after installing only the Skill.

An intranet Jira must be reachable from the machine running the MCP. Ask the user to connect the required company network or VPN when Jira cannot be reached.
