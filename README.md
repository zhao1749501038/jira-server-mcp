# Jira Server MCP

> Zero-dependency MCP server for self-hosted **Jira Server / Data Center** — works on Jira **8.x including pre-8.14** (no Personal Access Token needed).

零依赖的 Jira Server / Data Center MCP 服务端，用 Python 标准库手写实现，无需 `pip install` 任何第三方包，Python 3.8+ 即可运行。

本仓库同时提供可从 GitHub 安装的 Codex Skill。Skill 负责调用流程和安全边界，仓库根目录的 MCP 服务端负责实际连接 Jira。

## 公司同事快速安装

适用环境：macOS、Codex 桌面应用、已连接公司内网 VPN。

把下面这一句话完整发送给 Codex：

```text
请使用 $skill-installer 安装 https://github.com/zhao1749501038/jira-server-mcp/tree/main/skills/jira-mcp，安装成功后不要停止，立即读取新安装 Skill 的 references/setup.md 并继续配置 Jira MCP，Jira 地址为 https://21tb-jira.21tb.com，完成后验证本人身份并告诉我可以使用哪些能力。
```

随后按 macOS 系统弹窗依次输入本人的 Jira 用户名和密码。用户名正常显示，密码隐藏输入；不要把密码发送到聊天中。

安装流程会自动完成：

1. 安装 `jira-mcp` Skill。
2. 下载或更新本仓库的 MCP 服务端。
3. 将本人 Jira 密码保存到本人 macOS 钥匙串。
4. 验证 Jira 返回的是本人身份。
5. 写入 Codex MCP 配置，并把写操作设为执行前确认。
6. 告知可用能力和下一步操作。

配置完成后，按 AI 提示重启 Codex 桌面应用，再新建任务使用刚配置的 MCP 工具。

## 其他 Jira 地址安装

其他自建 Jira 可以发送下面这句话，把占位地址替换成实际 Jira 地址：

```text
请使用 $skill-installer 安装并继续配置这个 Jira Skill，不要在 Skill 安装完成后停止；Jira 地址为 <公司 Jira 地址>：https://github.com/zhao1749501038/jira-server-mcp/tree/main/skills/jira-mcp
```

Skill 和仓库均不包含任何人的真实账号、密码、Token 或客户端配置。

## 为什么需要它

- Atlassian 官方 MCP 只支持 Jira **Cloud**，不支持本地化部署
- 主流开源 `mcp-atlassian` 要求 Jira Server **8.14+**，因为它依赖 Personal Access Token (PAT)
- 很多企业仍在使用 8.13 及更早版本，**没有 PAT**，只能用 Basic Auth（用户名 + 密码）
- 本服务同时支持 **Basic Auth 与 PAT**，覆盖 8.x 全版本

## 提供的工具

| 工具 | 作用 |
|---|---|
| `jira_whoami` | 验证登录、查看当前账号 |
| `jira_get_projects` | 列出可见项目 |
| `jira_search_issues` | JQL 搜索 |
| `jira_get_issue` | 获取详情、最近评论和自定义字段 |
| `jira_get_create_fields` | 查询创建时的必填字段与枚举值 |
| `jira_prepare_issue` | 创建前只读预检，不写 Jira |
| `jira_create_issue` | 创建 Jira |
| `jira_get_edit_fields` | 查询当前允许编辑的字段 |
| `jira_update_issue` | 修改标准字段或自定义字段 |
| `jira_add_comment` | 添加评论 |
| `jira_get_transitions` | 查询当前可执行的状态流转 |
| `jira_transition_issue` | 执行状态流转 |
| `jira_assign_issue` | 修改负责人 |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `JIRA_BASE_URL` | 是 | Jira 地址，如 `https://jira.yourcompany.com` |
| `JIRA_USERNAME` | Basic Auth 必填 | Jira 用户名 |
| `JIRA_PASSWORD` | Basic Auth 使用 | Jira 密码；macOS 可由钥匙串替代 |
| `JIRA_TOKEN` | PAT 时使用 | Personal Access Token（8.14+），设置后优先使用 |
| `JIRA_KEYCHAIN_SERVICE` | macOS 可选 | 从系统钥匙串读取密码，可替代 `JIRA_PASSWORD` |
| `JIRA_CA_BUNDLE` | 否 | 公司内部 CA 证书文件路径 |
| `JIRA_SSL_VERIFY` | 否 | 默认 `true`；不建议关闭证书校验 |
| `JIRA_TIMEOUT` | 否 | 请求超时秒数，默认 30 |

> 认证方式：若设置了 `JIRA_TOKEN` 则用 Bearer Token（PAT），否则用 `JIRA_USERNAME` + `JIRA_PASSWORD` 做 Basic Auth；macOS 也可用 `JIRA_KEYCHAIN_SERVICE` 从本人钥匙串读取密码。

## 安装与运行

三种方式任选其一：

```bash
# 方式一：pipx 安装（推荐，全局可用 jira-server-mcp 命令）
pipx install git+https://github.com/zhao1749501038/jira-server-mcp

# 方式二：uvx 直接运行（不落盘）
uvx --from git+https://github.com/zhao1749501038/jira-server-mcp jira-server-mcp

# 方式三：直接运行源码（零依赖，连 pip 都不用）
git clone https://github.com/zhao1749501038/jira-server-mcp
python3 jira-server-mcp/jira_mcp_server.py
```

## 接入各 MCP 客户端

### WorkBuddy
`~/.workbuddy/mcp.json`：
```json
{
  "mcpServers": {
    "jira": {
      "command": "/usr/bin/python3",
      "args": ["/path/to/jira_mcp_server.py"],
      "env": {
        "JIRA_BASE_URL": "https://jira.yourcompany.com",
        "JIRA_USERNAME": "your-username",
        "JIRA_PASSWORD": "your-password"
      }
    }
  }
}
```

### Claude Code
```bash
claude mcp add --scope user jira \
  --env JIRA_BASE_URL=https://jira.yourcompany.com \
  --env JIRA_USERNAME=your-username --env JIRA_PASSWORD=your-password \
  -- /usr/bin/python3 /path/to/jira_mcp_server.py
```

### Claude Desktop
`~/Library/Application Support/Claude/claude_desktop_config.json`：
```json
{
  "mcpServers": {
    "jira": {
      "command": "/usr/bin/python3",
      "args": ["/path/to/jira_mcp_server.py"],
      "env": {
        "JIRA_BASE_URL": "https://jira.yourcompany.com",
        "JIRA_USERNAME": "your-username",
        "JIRA_PASSWORD": "your-password"
      }
    }
  }
}
```

### Cursor
`~/.cursor/mcp.json`，写法同 Claude Desktop。

### Codex
`~/.codex/config.toml`：
```toml
[mcp_servers.jira]
command = "/usr/bin/python3"
args = ["/path/to/jira_mcp_server.py"]
env = { JIRA_BASE_URL = "https://jira.yourcompany.com", JIRA_USERNAME = "your-username", JIRA_PASSWORD = "your-password" }
default_tools_approval_mode = "writes"
```

macOS 用户推荐使用一键安装器。它会把密码写入系统钥匙串，Codex 配置中不会出现密码：

```bash
python3 install_codex_macos.py \
  --url https://jira.yourcompany.com \
  --gui \
  --name jira
```

安装器会先验证本人 Jira 身份，再写入 Codex 配置，并将所有写操作设为执行前确认。完成后重启 Codex 桌面应用，再新建任务使用。

## 推荐调用流程

- 查询：直接使用 `jira_search_issues` 或 `jira_get_issue`
- 创建：`jira_get_create_fields` → `jira_prepare_issue` → 用户确认 → `jira_create_issue`
- 修改自定义字段：`jira_get_edit_fields` → 用户确认 → `jira_update_issue`
- 修改状态：`jira_get_transitions` → 用户确认 → `jira_transition_issue`
- 所有写入工具都会再次读取 Jira，返回实际结果和真实链接

## 安全提醒

- 不要把真实密码、Token、`.env` 或客户端个人配置提交到 Git。
- macOS 优先使用钥匙串；其他系统优先使用系统密钥管理或受控环境变量。
- 个人试用阶段使用本地 STDIO MCP，每个人配置自己的 Jira 身份，Jira 权限和操作人都与本人一致。
- 分享代码时只分享本仓库和安装说明，每位同事在自己的电脑上输入自己的账号密码。
- 团队后续如改为内网 HTTP MCP，必须实现逐用户认证和身份透传，不能让所有人共用一个个人账号。
- 服务端未提供删除工具。创建、修改、评论、指派和状态流转均标记为写操作，Codex 可配置为执行前确认。
- 公司内部证书应通过 `JIRA_CA_BUNDLE` 信任 CA；仅限临时诊断时考虑关闭证书校验。

## License

MIT
