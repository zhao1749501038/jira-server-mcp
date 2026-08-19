# Jira Server MCP

> Zero-dependency MCP server for self-hosted **Jira Server / Data Center** — works on Jira **8.x including pre-8.14** (no Personal Access Token needed).

零依赖的 Jira Server / Data Center MCP 服务端，用 Python 标准库手写实现，无需 `pip install` 任何第三方包，Python 3.8+ 即可运行。

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
| `jira_get_issue` | 获取需求/Bug 详情 |
| `jira_create_issue` | 创建 Jira |
| `jira_update_issue` | 修改标题/描述/优先级/标签 |
| `jira_add_comment` | 添加评论 |
| `jira_get_transitions` | 查询当前可执行的状态流转 |
| `jira_transition_issue` | 执行状态流转 |
| `jira_assign_issue` | 修改负责人 |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `JIRA_BASE_URL` | 是 | Jira 地址，如 `https://jira.yourcompany.com` |
| `JIRA_USERNAME` | Basic Auth 必填 | Jira 用户名 |
| `JIRA_PASSWORD` | Basic Auth 必填 | Jira 密码 |
| `JIRA_TOKEN` | PAT 时使用 | Personal Access Token（8.14+），设置后优先使用 |
| `JIRA_SSL_VERIFY` | 否 | 默认 `true`，自签证书报错时设 `false` |
| `JIRA_TIMEOUT` | 否 | 请求超时秒数，默认 30 |

> 认证方式：若设置了 `JIRA_TOKEN` 则用 Bearer Token（PAT），否则用 `JIRA_USERNAME` + `JIRA_PASSWORD` 做 Basic Auth。

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
```

## 安全提醒

- 凭据以明文形式写在客户端配置中，请勿提交到 Git；建议用专用 Bot 账号并按最小权限收敛（仅查看/创建/编辑/评论/流转/指派，不开删除与系统管理）。
- 若需多人共享，建议把服务端部署为 HTTP MCP Server 并统一鉴权，而不是每人各自存密码。

## License

MIT
