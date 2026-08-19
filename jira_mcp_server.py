#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jira Server / Data Center MCP Server（零依赖通用版）

一个用 Python 标准库手写的 MCP（Model Context Protocol）服务端，专为自托管 Jira
Server / Data Center 设计。无需 pip 安装任何第三方包，Python 3.8+ 即可运行。

为什么需要它：
- Atlassian 官方 MCP 只支持 Jira Cloud，不支持本地化部署
- 主流开源 mcp-atlassian 要求 Jira Server 8.14+（依赖 Personal Access Token）
- 很多企业仍在用 8.13 及更早版本，没有 PAT，只能用 Basic Auth（用户名+密码）
- 本服务同时支持 Basic Auth 与 PAT，覆盖 8.x 全版本

环境变量：
  JIRA_BASE_URL     Jira 地址，如 https://jira.yourcompany.com（必填）
  JIRA_USERNAME     Jira 用户名（Basic Auth 时必填）
  JIRA_PASSWORD     Jira 密码（Basic Auth 时必填）
  JIRA_TOKEN        Personal Access Token（8.14+，设置后优先使用，覆盖账号密码）
  JIRA_SSL_VERIFY   是否校验证书，默认 true；自签证书报错时设 false
  JIRA_TIMEOUT      请求超时秒数，默认 30
"""

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME", "")
JIRA_PASSWORD = os.environ.get("JIRA_PASSWORD", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
SSL_VERIFY = os.environ.get("JIRA_SSL_VERIFY", "true").lower() != "false"
TIMEOUT = int(os.environ.get("JIRA_TIMEOUT", "30"))

SSL_CTX = ssl.create_default_context() if SSL_VERIFY else ssl._create_unverified_context()

SERVER_NAME = "jira-server-mcp"
SERVER_VERSION = "1.0.0"


class JiraError(Exception):
    pass


def _check_auth():
    if not JIRA_BASE_URL:
        raise JiraError("未配置 JIRA_BASE_URL，请在 MCP 配置 env 中填写 Jira 地址")
    if not JIRA_TOKEN and not (JIRA_USERNAME and JIRA_PASSWORD):
        raise JiraError(
            "未配置 Jira 凭据：请设置 JIRA_TOKEN（PAT，8.14+）或 "
            "JIRA_USERNAME + JIRA_PASSWORD（Basic Auth）"
        )


def _auth_header():
    if JIRA_TOKEN:
        return f"Bearer {JIRA_TOKEN}"
    token = base64.b64encode(f"{JIRA_USERNAME}:{JIRA_PASSWORD}".encode()).decode()
    return f"Basic {token}"


def _request(method, path, body=None, params=None):
    _check_auth()
    url = f"{JIRA_BASE_URL}/rest/api/2{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header())
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            err = json.loads(e.read().decode("utf-8"))
            msgs = [m for m in err.get("errorMessages", []) if m]
            for k, v in (err.get("errors") or {}).items():
                msgs.append(f"{k}: {v}")
            detail = "; ".join(msgs) or "无详细错误信息"
        except Exception:
            detail = "无详细错误信息"
        raise JiraError(f"Jira API 返回 {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        msg = str(getattr(e, "reason", e))
        if "CERTIFICATE" in msg.upper() or "SSL" in msg.upper():
            msg += "（公司自签证书可将 JIRA_SSL_VERIFY 设为 false）"
        raise JiraError(f"无法连接 Jira（{JIRA_BASE_URL}）：{msg}") from e


def _user_name(user):
    return (user or {}).get("displayName") or (user or {}).get("name")


def _simplify_issue(issue, detail=False):
    f = issue.get("fields", {}) if issue else {}
    out = {
        "key": issue.get("key"),
        "summary": f.get("summary"),
        "type": ((f.get("issuetype") or {}).get("name")),
        "status": ((f.get("status") or {}).get("name")),
        "priority": ((f.get("priority") or {}).get("name")),
        "assignee": _user_name(f.get("assignee")),
        "reporter": _user_name(f.get("reporter")),
        "updated": f.get("updated"),
    }
    if detail:
        out["description"] = f.get("description")
        out["created"] = f.get("created")
        out["labels"] = f.get("labels")
        out["url"] = f"{JIRA_BASE_URL}/browse/{issue.get('key')}"
    return out


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------- 工具实现 ----------

def t_whoami():
    return _dump(_request("GET", "/myself"))


def t_get_projects():
    projects = _request("GET", "/project")
    return _dump([{"key": p.get("key"), "name": p.get("name")} for p in projects])


def t_search_issues(jql, max_results=20):
    data = _request("GET", "/search", params={
        "jql": jql,
        "maxResults": min(int(max_results), 50),
        "fields": "summary,status,assignee,reporter,priority,issuetype,updated",
    })
    return _dump({
        "total": data.get("total"),
        "issues": [_simplify_issue(i) for i in data.get("issues", [])],
    })


def t_get_issue(issue_key):
    return _dump(_simplify_issue(_request("GET", f"/issue/{issue_key}"), detail=True))


def t_create_issue(project, issue_type, summary, description="", assignee=None,
                   priority=None, labels=None):
    fields = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    if description:
        fields["description"] = description
    if assignee:
        fields["assignee"] = {"name": assignee}
    if priority:
        fields["priority"] = {"name": priority}
    if labels:
        fields["labels"] = labels
    result = _request("POST", "/issue", body={"fields": fields})
    return _dump({
        "key": result.get("key"),
        "url": f"{JIRA_BASE_URL}/browse/{result.get('key')}",
        "message": "创建成功",
    })


def t_update_issue(issue_key, summary=None, description=None, priority=None, labels=None):
    fields = {}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        fields["description"] = description
    if priority is not None:
        fields["priority"] = {"name": priority}
    if labels is not None:
        fields["labels"] = labels
    if not fields:
        raise JiraError("没有需要修改的字段，请至少传入 summary/description/priority/labels 之一")
    _request("PUT", f"/issue/{issue_key}", body={"fields": fields})
    return _dump({"key": issue_key, "message": "更新成功", "updated_fields": list(fields.keys())})


def t_add_comment(issue_key, comment):
    result = _request("POST", f"/issue/{issue_key}/comment", body={"body": comment})
    return _dump({"key": issue_key, "comment_id": result.get("id"), "message": "评论已添加"})


def t_get_transitions(issue_key):
    data = _request("GET", f"/issue/{issue_key}/transitions")
    return _dump([
        {"id": t.get("id"), "name": t.get("name"), "to_status": ((t.get("to") or {}).get("name"))}
        for t in data.get("transitions", [])
    ])


def t_transition_issue(issue_key, transition, comment=None):
    data = _request("GET", f"/issue/{issue_key}/transitions")
    matched = None
    for t in data.get("transitions", []):
        if str(transition) in (str(t.get("id")), t.get("name")):
            matched = t
            break
    if not matched:
        available = [t.get("name") for t in data.get("transitions", [])]
        raise JiraError(f"找不到流转 '{transition}'，当前可用：{available}")
    payload = {"transition": {"id": matched["id"]}}
    if comment:
        payload["update"] = {"comment": [{"add": {"body": comment}}]}
    _request("POST", f"/issue/{issue_key}/transitions", body=payload)
    return _dump({"key": issue_key, "transition": matched.get("name"), "message": "状态已流转"})


def t_assign_issue(issue_key, assignee):
    _request("PUT", f"/issue/{issue_key}/assignee", body={"name": assignee})
    return _dump({"key": issue_key, "assignee": assignee, "message": "负责人已修改"})


S = {"type": "string"}


def _schema(props, required):
    return {"type": "object", "properties": props, "required": required}


TOOLS = [
    {"name": "jira_whoami", "description": "验证登录：返回当前 Jira 账号信息。用于测试凭据是否配置正确。",
     "inputSchema": _schema({}, []), "fn": lambda a: t_whoami()},
    {"name": "jira_get_projects", "description": "列出当前账号有权限查看的所有 Jira 项目（key 和名称）。",
     "inputSchema": _schema({}, []), "fn": lambda a: t_get_projects()},
    {"name": "jira_search_issues",
     "description": "按 JQL 搜索 Jira。示例：project = XYZ AND assignee = currentUser() AND status != Closed ORDER BY updated DESC",
     "inputSchema": _schema({"jql": S, "max_results": {"type": "integer", "default": 20}}, ["jql"]),
     "fn": lambda a: t_search_issues(a["jql"], a.get("max_results", 20))},
    {"name": "jira_get_issue",
     "description": "获取某个需求/Bug 的详情（标题、描述、状态、负责人、优先级、链接等）。issue_key 形如 XYZ-123。",
     "inputSchema": _schema({"issue_key": S}, ["issue_key"]),
     "fn": lambda a: t_get_issue(a["issue_key"])},
    {"name": "jira_create_issue",
     "description": "创建 Jira。project 为项目 key，issue_type 填类型名称（如 任务/故事/Bug），assignee 填用户名，priority 填优先级名称。",
     "inputSchema": _schema({
         "project": S, "issue_type": S, "summary": S, "description": S,
         "assignee": S, "priority": S, "labels": {"type": "array", "items": S},
     }, ["project", "issue_type", "summary"]),
     "fn": lambda a: t_create_issue(
         a["project"], a["issue_type"], a["summary"], description=a.get("description", ""),
         assignee=a.get("assignee"), priority=a.get("priority"), labels=a.get("labels"))},
    {"name": "jira_update_issue",
     "description": "修改 Jira 的标题、描述、优先级或标签，未传的字段保持不变。",
     "inputSchema": _schema({
         "issue_key": S, "summary": S, "description": S, "priority": S,
         "labels": {"type": "array", "items": S},
     }, ["issue_key"]),
     "fn": lambda a: t_update_issue(
         a["issue_key"], summary=a.get("summary"), description=a.get("description"),
         priority=a.get("priority"), labels=a.get("labels"))},
    {"name": "jira_add_comment", "description": "给 Jira 添加评论。",
     "inputSchema": _schema({"issue_key": S, "comment": S}, ["issue_key", "comment"]),
     "fn": lambda a: t_add_comment(a["issue_key"], a["comment"])},
    {"name": "jira_get_transitions",
     "description": "获取该 Jira 当前工作流允许执行的状态流转列表。不要假设状态名，先查这个。",
     "inputSchema": _schema({"issue_key": S}, ["issue_key"]),
     "fn": lambda a: t_get_transitions(a["issue_key"])},
    {"name": "jira_transition_issue",
     "description": "执行状态流转。transition 填流转名称或 id，建议先调用 jira_get_transitions 查可用值。",
     "inputSchema": _schema({"issue_key": S, "transition": S, "comment": S}, ["issue_key", "transition"]),
     "fn": lambda a: t_transition_issue(a["issue_key"], a["transition"], comment=a.get("comment"))},
    {"name": "jira_assign_issue", "description": "修改 Jira 负责人。assignee 填 Jira 用户名（登录名）。",
     "inputSchema": _schema({"issue_key": S, "assignee": S}, ["issue_key", "assignee"]),
     "fn": lambda a: t_assign_issue(a["issue_key"], a["assignee"])},
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# ---------- MCP stdio 传输层（JSON-RPC 2.0，按行分隔） ----------

def _send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    is_request = msg_id is not None

    if method == "initialize":
        client_ver = (msg.get("params") or {}).get("protocolVersion", "2024-11-05")
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": client_ver,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }})
    elif method in ("notifications/initialized",) or (method is None and not is_request):
        pass
    elif method == "tools/list":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "tools": [{"name": t["name"], "description": t["description"],
                       "inputSchema": t["inputSchema"]} for t in TOOLS]}})
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS_BY_NAME.get(name)
        if not tool:
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"未知工具: {name}"}], "isError": True}})
            return
        try:
            text = tool["fn"](args)
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": text}]}})
        except JiraError as e:
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"Jira 调用失败：{e}"}], "isError": True}})
        except KeyError as e:
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"缺少必填参数: {e}"}], "isError": True}})
        except Exception as e:
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"工具执行异常：{type(e).__name__}: {e}"}],
                "isError": True}})
    elif method == "ping":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
    elif is_request:
        _send({"jsonrpc": "2.0", "id": msg_id, "error": {
            "code": -32601, "message": f"Method not supported: {method}"}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            _handle(json.loads(line))
        except Exception as e:
            print(f"[{SERVER_NAME}] message error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
