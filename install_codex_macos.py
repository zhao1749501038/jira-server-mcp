#!/usr/bin/env python3
"""为 macOS 用户安装 Jira MCP 到 Codex，并将密码保存到系统钥匙串。"""

import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def codex_exists(codex, name):
    result = subprocess.run(
        [codex, "mcp", "get", name, "--json"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def set_writes_approval(config_path, name):
    text = config_path.read_text(encoding="utf-8")
    header = f"[mcp_servers.{name}]"
    start = text.find(header)
    if start < 0:
        raise RuntimeError(f"未在 {config_path} 找到 {header}")
    content_start = start + len(header)
    next_table = text.find("\n[", content_start)
    block_end = len(text) if next_table < 0 else next_table
    block = text[content_start:block_end]
    line = '\ndefault_tools_approval_mode = "writes"'
    if "default_tools_approval_mode" not in block:
        text = text[:content_start] + line + text[content_start:]
        config_path.write_text(text, encoding="utf-8")


def verify_server(command, env):
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=env,
    )
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "jira-mcp-installer", "version": "1"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "jira_whoami", "arguments": {},
        }},
    ]
    try:
        for message in messages:
            proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        initialize = json.loads(proc.stdout.readline())
        identity = json.loads(proc.stdout.readline())
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    content = identity.get("result", {}).get("content", [])
    if not content or identity.get("result", {}).get("isError"):
        raise RuntimeError("Jira 登录验证失败：" + str(content))
    user = json.loads(content[0]["text"])
    return initialize["result"]["serverInfo"], user


def main():
    parser = argparse.ArgumentParser(description="安装 Jira MCP 到 Codex（macOS）")
    parser.add_argument("--url", required=True, help="Jira 地址")
    parser.add_argument("--username", required=True, help="Jira 登录名")
    parser.add_argument("--name", default="jira", help="Codex 中显示的 MCP 名称")
    parser.add_argument("--replace", action="store_true", help="替换已有的同名 MCP 配置")
    args = parser.parse_args()

    if sys.platform != "darwin" or not Path("/usr/bin/security").exists():
        parser.error("该安装器仅支持 macOS，其他系统请按照 README 使用环境变量或 PAT")

    codex = shutil.which("codex")
    if not codex:
        parser.error("未找到 codex 命令，请先安装或打开 Codex 桌面应用")

    source = Path(__file__).with_name("jira_mcp_server.py").resolve()
    if not source.exists():
        parser.error(f"未找到 MCP 服务端文件：{source}")

    existing = codex_exists(codex, args.name)
    if existing and not args.replace:
        parser.error(f"Codex 已存在 {args.name}，确认替换时请加 --replace")

    host = urllib.parse.urlparse(args.url).hostname or "jira"
    service = f"jira-server-mcp:{host}"
    password = getpass.getpass("请输入 Jira 密码，输入内容不会显示：")
    if not password:
        parser.error("密码不能为空")

    run([
        "/usr/bin/security", "add-generic-password", "-U",
        "-s", service, "-a", args.username, "-w", password,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    env = os.environ.copy()
    env.update({
        "JIRA_BASE_URL": args.url.rstrip("/"),
        "JIRA_USERNAME": args.username,
        "JIRA_KEYCHAIN_SERVICE": service,
        "JIRA_SSL_VERIFY": "true",
    })
    server_info, user = verify_server([sys.executable, str(source)], env)

    if existing:
        run([codex, "mcp", "remove", args.name], stdout=subprocess.DEVNULL)
    run([
        codex, "mcp", "add", args.name,
        "--env", f"JIRA_BASE_URL={args.url.rstrip('/')}",
        "--env", f"JIRA_USERNAME={args.username}",
        "--env", f"JIRA_KEYCHAIN_SERVICE={service}",
        "--env", "JIRA_SSL_VERIFY=true",
        "--", sys.executable, str(source),
    ], stdout=subprocess.DEVNULL)
    set_writes_approval(Path.home() / ".codex" / "config.toml", args.name)

    print(f"已连接 Jira：{user.get('display_name')}（{user.get('username')}）")
    print(f"MCP 服务端：{server_info.get('name')} {server_info.get('version')}")
    print(f"Codex 配置：{args.name}，写入操作设为执行前确认")
    print("请重启 Codex 桌面应用或新建任务后使用。")


if __name__ == "__main__":
    main()
