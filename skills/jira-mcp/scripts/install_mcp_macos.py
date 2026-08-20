#!/usr/bin/env python3
"""After explicit approval, download and configure jira-server-mcp for Codex."""

import argparse
from pathlib import Path
import subprocess
import sys


REPOSITORY = "https://github.com/zhao1749501038/jira-server-mcp.git"


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def prepare_repository(target):
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run([
            "git", "clone", "--branch", "main", "--single-branch",
            REPOSITORY, str(target),
        ])
        return

    if not (target / ".git").is_dir():
        raise RuntimeError(f"Target exists but is not a Git repository: {target}")
    remote = subprocess.check_output(
        ["git", "-C", str(target), "remote", "get-url", "origin"], text=True
    ).strip()
    if remote.rstrip("/") != REPOSITORY.rstrip("/"):
        raise RuntimeError(f"Existing repository has a different origin: {remote}")
    status = subprocess.check_output(
        ["git", "-C", str(target), "status", "--porcelain"], text=True
    )
    if status.strip():
        raise RuntimeError(f"Existing repository has uncommitted changes: {target}")
    run(["git", "-C", str(target), "pull", "--ff-only", "origin", "main"])


def main():
    parser = argparse.ArgumentParser(
        description="Download and configure Jira MCP for Codex on macOS"
    )
    parser.add_argument("--url", required=True, help="Jira base URL")
    parser.add_argument("--username", required=True, help="Current user's Jira username")
    parser.add_argument("--name", default="jira", help="MCP name shown in Codex")
    parser.add_argument(
        "--target", type=Path, default=Path.home() / "projects" / "jira-server-mcp",
        help="Local checkout used to run the MCP server",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Confirm repository, Keychain, and Codex configuration changes",
    )
    args = parser.parse_args()

    if sys.platform != "darwin":
        parser.error("This setup script currently supports macOS only")
    if not args.confirm:
        parser.error(
            "Setup is not confirmed. Explain the changes and obtain approval before adding --confirm"
        )

    target = args.target.expanduser().resolve()
    prepare_repository(target)
    installer = target / "install_codex_macos.py"
    if not installer.exists():
        raise RuntimeError(f"Missing installer in downloaded repository: {installer}")

    command = [
        "/usr/bin/python3", str(installer),
        "--url", args.url,
        "--username", args.username,
        "--name", args.name,
    ]
    existing = subprocess.run(
        ["codex", "mcp", "get", args.name, "--json"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if existing.returncode == 0:
        command.append("--replace")
    run(command)


if __name__ == "__main__":
    main()
