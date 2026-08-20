# macOS Codex setup

Use this reference only when the user asks to install, configure, repair, or share the Jira MCP.

## Changes made by setup

The setup script will:

1. Clone or update `zhao1749501038/jira-server-mcp` under the current user's `~/projects` directory.
2. Prompt for the current user's Jira password without displaying it.
3. Store the password in the current user's macOS Keychain.
4. Verify the Jira identity with `jira_whoami`.
5. Add the local STDIO MCP to `~/.codex/config.toml` and require confirmation for write tools.

Explain these changes and obtain the user's approval before running setup.

## Run setup

From this Skill directory, run:

```bash
python3 scripts/install_mcp_macos.py \
  --url <Jira base URL> \
  --username <current user's Jira username> \
  --confirm
```

The password must be entered by the user in the interactive terminal. Never accept it in a chat message or add it to the command line.

If an intranet Jira is unreachable, ask the user to connect the company network or VPN and retry. Do not disable TLS verification as a general workaround.

After setup, start a new Codex task or restart the desktop app, then call `jira_whoami` and confirm that it matches the current user.
