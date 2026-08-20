# macOS Codex setup

Use this reference only when the user asks to install, configure, repair, or share the Jira MCP.

## Changes made by setup

The setup script will:

1. Clone or update `zhao1749501038/jira-server-mcp` under the current user's `~/projects` directory.
2. Open macOS system dialogs for the current user's Jira username and hidden password.
3. Store the password in the current user's macOS Keychain.
4. Verify the Jira identity with `jira_whoami`.
5. Add the local STDIO MCP to `~/.codex/config.toml` and require confirmation for write tools.

An explicit request to install and configure this Skill authorizes these setup actions. Briefly explain the changes, then continue without asking for a second confirmation unless the target or requested identity is unclear.

## Run setup

From this Skill directory, run:

```bash
python3 scripts/install_mcp_macos.py \
  --url <Jira base URL> \
  --confirm
```

The setup opens macOS dialogs for the username and password. The password field is hidden. Never accept a password in chat or add it to the command line.

If an intranet Jira is unreachable, ask the user to connect the company network or VPN and retry. Do not disable TLS verification as a general workaround.

After setup, report the identity returned by the installer and explain the available query and write capabilities. Ask the user to restart the Codex desktop app, then start a new task so the newly configured MCP tools are loaded. In that task, call `jira_whoami` before the first write.
