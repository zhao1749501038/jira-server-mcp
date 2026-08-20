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
  JIRA_KEYCHAIN_SERVICE  macOS 钥匙串服务名，可替代 JIRA_PASSWORD
  JIRA_CA_BUNDLE    公司 CA 证书文件路径（可选）
  JIRA_SSL_VERIFY   是否校验证书，默认 true
  JIRA_TIMEOUT      请求超时秒数，默认 30
"""

import base64
import functools
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME", "")
JIRA_PASSWORD = os.environ.get("JIRA_PASSWORD", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
JIRA_KEYCHAIN_SERVICE = os.environ.get("JIRA_KEYCHAIN_SERVICE", "")
JIRA_CA_BUNDLE = os.environ.get("JIRA_CA_BUNDLE", "")
SSL_VERIFY = os.environ.get("JIRA_SSL_VERIFY", "true").lower() != "false"
try:
    TIMEOUT = max(1, min(int(os.environ.get("JIRA_TIMEOUT", "30")), 300))
except ValueError:
    TIMEOUT = 30

SSL_CTX = (
    ssl.create_default_context(cafile=JIRA_CA_BUNDLE or None)
    if SSL_VERIFY
    else ssl._create_unverified_context()
)

SERVER_NAME = "jira-server-mcp"
SERVER_VERSION = "1.2.0"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INSTRUCTIONS = (
    "查询工具可直接使用。创建、修改、评论、指派或状态流转前，必须先向用户展示准确变化并取得确认。"
    "创建前先调用 jira_prepare_issue；修改自定义字段前先调用 jira_get_edit_fields；"
    "状态变化前先调用 jira_get_transitions。禁止猜测字段 ID 或可用状态。本服务不提供删除能力。"
)
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$", re.IGNORECASE)


class JiraError(Exception):
    pass


def _check_auth():
    if not JIRA_BASE_URL:
        raise JiraError("未配置 JIRA_BASE_URL，请在 MCP 配置 env 中填写 Jira 地址")
    if not JIRA_TOKEN and not (
        JIRA_USERNAME and (JIRA_PASSWORD or JIRA_KEYCHAIN_SERVICE)
    ):
        raise JiraError(
            "未配置 Jira 凭据：请设置 JIRA_TOKEN（PAT，8.14+）或 "
            "JIRA_USERNAME + JIRA_PASSWORD（Basic Auth）；macOS 也可使用 "
            "JIRA_USERNAME + JIRA_KEYCHAIN_SERVICE 从钥匙串读取密码"
        )


@functools.lru_cache(maxsize=1)
def _resolved_password():
    if JIRA_PASSWORD:
        return JIRA_PASSWORD
    if not JIRA_KEYCHAIN_SERVICE:
        return ""
    security = "/usr/bin/security"
    if not os.path.exists(security):
        raise JiraError("当前系统不支持 macOS 钥匙串，请改用 JIRA_PASSWORD 或 JIRA_TOKEN")
    try:
        result = subprocess.run(
            [security, "find-generic-password", "-s", JIRA_KEYCHAIN_SERVICE,
             "-a", JIRA_USERNAME, "-w"],
            check=True, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise JiraError(
            f"无法从 macOS 钥匙串读取 Jira 密码，请检查服务名 {JIRA_KEYCHAIN_SERVICE} "
            f"和账号 {JIRA_USERNAME}"
        ) from exc
    return result.stdout.rstrip("\r\n")


def _auth_header():
    if JIRA_TOKEN:
        return f"Bearer {JIRA_TOKEN}"
    token = base64.b64encode(
        f"{JIRA_USERNAME}:{_resolved_password()}".encode()
    ).decode()
    return f"Basic {token}"


def _issue_key(value):
    key = str(value or "").strip().upper()
    if not ISSUE_KEY_RE.fullmatch(key):
        raise JiraError(f"Jira 编号格式不正确：{value}")
    return key


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
        login_reason = e.headers.get("X-Seraph-LoginReason", "")
        if login_reason == "AUTHENTICATION_DENIED":
            detail = "Jira 已拒绝认证，账号可能触发验证码或被锁定"
        raise JiraError(f"Jira API 返回 {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        msg = str(getattr(e, "reason", e))
        if "CERTIFICATE" in msg.upper() or "SSL" in msg.upper():
            msg += "（请优先通过 JIRA_CA_BUNDLE 配置公司 CA 证书）"
        raise JiraError(f"无法连接 Jira（{JIRA_BASE_URL}）：{msg}") from e


def _user_name(user):
    return (user or {}).get("displayName") or (user or {}).get("name")


def _simple_value(value):
    if isinstance(value, list):
        return [_simple_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "displayName" in value:
        return {
            "username": value.get("name") or value.get("key"),
            "display_name": value.get("displayName"),
        }
    for key in ("value", "name", "key", "id"):
        if value.get(key) is not None:
            return value.get(key)
    return {
        key: _simple_value(item)
        for key, item in value.items()
        if key not in ("self", "avatarUrls", "iconUrl")
    }


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
        out["due_date"] = f.get("duedate")
        out["labels"] = f.get("labels")
        out["components"] = [c.get("name") for c in (f.get("components") or [])]
        out["fix_versions"] = [v.get("name") for v in (f.get("fixVersions") or [])]
        comments = ((f.get("comment") or {}).get("comments") or [])
        out["comments"] = [
            {
                "id": comment.get("id"),
                "author": _user_name(comment.get("author")),
                "created": comment.get("created"),
                "updated": comment.get("updated"),
                "body": comment.get("body"),
            }
            for comment in comments
        ]
        names = issue.get("names") or {}
        custom_fields = {}
        for field_id, value in f.items():
            if not field_id.startswith("customfield_") or value in (None, "", []):
                continue
            custom_fields[field_id] = {
                "name": names.get(field_id, field_id),
                "value": _simple_value(value),
            }
        out["custom_fields"] = custom_fields
        out["url"] = f"{JIRA_BASE_URL}/browse/{issue.get('key')}"
    return out


def _issue_snapshot(issue_key, detail=False):
    key = _issue_key(issue_key)
    params = {
        "fields": "*all" if detail else "summary,status,assignee,priority,updated",
    }
    if detail:
        params["expand"] = "names"
    issue = _request(
        "GET", f"/issue/{urllib.parse.quote(key, safe='')}", params=params
    )
    out = _simplify_issue(issue, detail=detail)
    out["url"] = f"{JIRA_BASE_URL}/browse/{key}"
    return out


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------- 工具实现 ----------

def t_whoami():
    user = _request("GET", "/myself")
    return _dump({
        "username": user.get("name") or user.get("key"),
        "display_name": user.get("displayName"),
        "email": user.get("emailAddress"),
        "active": user.get("active"),
    })


def t_get_projects():
    projects = _request("GET", "/project")
    return _dump([
        {"id": p.get("id"), "key": p.get("key"), "name": p.get("name")}
        for p in projects
    ])


def t_search_issues(jql, max_results=20):
    if not str(jql or "").strip():
        raise JiraError("JQL 不能为空")
    data = _request("GET", "/search", params={
        "jql": jql,
        "maxResults": max(1, min(int(max_results), 50)),
        "fields": "summary,status,assignee,reporter,priority,issuetype,updated",
    })
    return _dump({
        "total": data.get("total"),
        "issues": [_simplify_issue(i) for i in data.get("issues", [])],
    })


def t_get_issue(issue_key, comment_limit=10, include_custom_fields=True):
    key = _issue_key(issue_key)
    issue = _request(
        "GET", f"/issue/{urllib.parse.quote(key, safe='')}",
        params={"expand": "names", "fields": "*all"},
    )
    result = _simplify_issue(issue, detail=True)
    limit = max(0, min(int(comment_limit), 50))
    result["comments"] = result.get("comments", [])[-limit:] if limit else []
    if not include_custom_fields:
        result.pop("custom_fields", None)
    return _dump(result)


def _find_issue_type(project, issue_type):
    project_value = urllib.parse.quote(str(project).strip(), safe="")
    data = _request("GET", f"/issue/createmeta/{project_value}/issuetypes")
    values = data.get("values", data if isinstance(data, list) else [])
    wanted = str(issue_type).strip().casefold()
    for item in values:
        if str(item.get("id")) == str(issue_type) or str(item.get("name", "")).casefold() == wanted:
            return item
    available = [item.get("name") for item in values]
    raise JiraError(f"项目 {project} 中找不到类型 {issue_type}，可用类型：{available}")


def _create_field_metadata(project, issue_type):
    issue_type_info = _find_issue_type(project, issue_type)
    project_value = urllib.parse.quote(str(project).strip(), safe="")
    issue_type_id = urllib.parse.quote(str(issue_type_info.get("id")), safe="")
    data = _request(
        "GET", f"/issue/createmeta/{project_value}/issuetypes/{issue_type_id}"
    )
    values = data.get("values", data if isinstance(data, list) else [])
    return issue_type_info, values


def _field_summary(field_id, info):
    allowed = info.get("allowedValues") or []
    return {
        "id": field_id,
        "name": info.get("name"),
        "required": bool(info.get("required")),
        "has_default": bool(info.get("hasDefaultValue")),
        "type": (info.get("schema") or {}).get("type"),
        "items": (info.get("schema") or {}).get("items"),
        "allowed_values": [_simple_value(value) for value in allowed[:100]],
    }


def t_get_create_fields(project, issue_type):
    issue_type_info, fields = _create_field_metadata(project, issue_type)
    return _dump({
        "project": project,
        "issue_type": {"id": issue_type_info.get("id"), "name": issue_type_info.get("name")},
        "fields": [_field_summary(field.get("fieldId"), field) for field in fields],
    })


def t_get_edit_fields(issue_key):
    key = _issue_key(issue_key)
    data = _request("GET", f"/issue/{urllib.parse.quote(key, safe='')}/editmeta")
    return _dump({
        "key": key,
        "fields": [
            _field_summary(field_id, info)
            for field_id, info in (data.get("fields") or {}).items()
        ],
    })


def _build_create_payload(project, issue_type, summary, description="", assignee=None,
                          priority=None, labels=None, components=None, extra_fields=None):
    issue_type_info, metadata = _create_field_metadata(project, issue_type)
    fields = {
        "project": {"key": project},
        "issuetype": {"id": issue_type_info.get("id")},
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
    if components:
        fields["components"] = [{"name": name} for name in components]
    if extra_fields:
        fields.update(extra_fields)

    metadata_by_id = {field.get("fieldId"): field for field in metadata}
    reporter = metadata_by_id.get("reporter") or {}
    if reporter.get("required") and not reporter.get("hasDefaultValue") and "reporter" not in fields:
        user = _request("GET", "/myself")
        fields["reporter"] = {"name": user.get("name") or user.get("key")}

    missing = []
    for field_id, info in metadata_by_id.items():
        if info.get("required") and not info.get("hasDefaultValue") and field_id not in fields:
            missing.append({"id": field_id, "name": info.get("name")})
    return fields, missing


def t_prepare_issue(project, issue_type, summary, description="", assignee=None,
                    priority=None, labels=None, components=None, extra_fields=None):
    fields, missing = _build_create_payload(
        project, issue_type, summary, description=description, assignee=assignee,
        priority=priority, labels=labels, components=components, extra_fields=extra_fields,
    )
    return _dump({
        "ready": not missing,
        "missing_required_fields": missing,
        "fields": fields,
        "message": "字段完整，可以在用户确认后创建" if not missing else "请先补充必填字段",
    })


def t_create_issue(project, issue_type, summary, description="", assignee=None,
                   priority=None, labels=None, components=None, extra_fields=None):
    fields, missing = _build_create_payload(
        project, issue_type, summary, description=description, assignee=assignee,
        priority=priority, labels=labels, components=components, extra_fields=extra_fields,
    )
    if missing:
        raise JiraError(
            "创建字段不完整：" + ", ".join(
                f"{item['name']}({item['id']})" for item in missing
            ) + "。请先调用 jira_get_create_fields 或 jira_prepare_issue"
        )
    result = _request("POST", "/issue", body={"fields": fields})
    key = result.get("key")
    return _dump({
        "key": key,
        "url": f"{JIRA_BASE_URL}/browse/{key}",
        "message": "创建成功",
        "verified_issue": _issue_snapshot(key, detail=True),
    })


def t_update_issue(issue_key, summary=None, description=None, priority=None, labels=None,
                   extra_fields=None):
    key = _issue_key(issue_key)
    fields = {}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        fields["description"] = description
    if priority is not None:
        fields["priority"] = {"name": priority}
    if labels is not None:
        fields["labels"] = labels
    if extra_fields:
        fields.update(extra_fields)
    if not fields:
        raise JiraError("没有需要修改的字段，请至少传入一个字段")
    _request("PUT", f"/issue/{urllib.parse.quote(key, safe='')}", body={"fields": fields})
    return _dump({
        "key": key,
        "message": "更新成功",
        "updated_fields": list(fields.keys()),
        "verified_issue": _issue_snapshot(key, detail=True),
    })


def t_add_comment(issue_key, comment):
    key = _issue_key(issue_key)
    result = _request(
        "POST", f"/issue/{urllib.parse.quote(key, safe='')}/comment", body={"body": comment}
    )
    return _dump({
        "key": key,
        "comment_id": result.get("id"),
        "message": "评论已添加",
        "verified_issue": _issue_snapshot(key, detail=True),
    })


def t_get_transitions(issue_key):
    key = _issue_key(issue_key)
    data = _request("GET", f"/issue/{urllib.parse.quote(key, safe='')}/transitions")
    return _dump([
        {"id": t.get("id"), "name": t.get("name"), "to_status": ((t.get("to") or {}).get("name"))}
        for t in data.get("transitions", [])
    ])


def t_transition_issue(issue_key, transition, comment=None):
    key = _issue_key(issue_key)
    data = _request("GET", f"/issue/{urllib.parse.quote(key, safe='')}/transitions")
    matched = None
    wanted = str(transition).strip().casefold()
    for t in data.get("transitions", []):
        candidates = {
            str(t.get("id", "")).casefold(),
            str(t.get("name", "")).casefold(),
            str((t.get("to") or {}).get("name", "")).casefold(),
        }
        if wanted in candidates:
            matched = t
            break
    if not matched:
        available = [t.get("name") for t in data.get("transitions", [])]
        raise JiraError(f"找不到流转 '{transition}'，当前可用：{available}")
    payload = {"transition": {"id": matched["id"]}}
    if comment:
        payload["update"] = {"comment": [{"add": {"body": comment}}]}
    _request(
        "POST", f"/issue/{urllib.parse.quote(key, safe='')}/transitions", body=payload
    )
    return _dump({
        "key": key,
        "transition": matched.get("name"),
        "target_status": (matched.get("to") or {}).get("name"),
        "message": "状态已流转",
        "verified_issue": _issue_snapshot(key),
    })


def t_assign_issue(issue_key, assignee):
    key = _issue_key(issue_key)
    _request(
        "PUT", f"/issue/{urllib.parse.quote(key, safe='')}/assignee",
        body={"name": assignee},
    )
    return _dump({
        "key": key,
        "assignee": assignee,
        "message": "负责人已修改",
        "verified_issue": _issue_snapshot(key),
    })


S = {"type": "string"}
B = {"type": "boolean"}
STRING_LIST = {"type": "array", "items": S}
EXTRA_FIELDS = {
    "type": "object",
    "description": "按 Jira 字段 ID 传入的额外字段，例如 customfield_12345；先查询创建或编辑字段后再使用。",
    "additionalProperties": True,
}


def _schema(props, required):
    return {
        "type": "object", "properties": props, "required": required,
        "additionalProperties": False,
    }


READ_ONLY = {
    "readOnlyHint": True, "destructiveHint": False,
    "idempotentHint": True, "openWorldHint": True,
}
WRITE_CREATE = {
    "readOnlyHint": False, "destructiveHint": False,
    "idempotentHint": False, "openWorldHint": True,
}
WRITE_UPDATE = {
    "readOnlyHint": False, "destructiveHint": True,
    "idempotentHint": False, "openWorldHint": True,
}


def _tool(name, description, schema, fn, annotations):
    return {
        "name": name, "description": description, "inputSchema": schema,
        "fn": fn, "annotations": annotations,
    }


TOOLS = [
    _tool("jira_whoami", "验证当前 Jira 登录身份。", _schema({}, []),
          lambda a: t_whoami(), READ_ONLY),
    _tool("jira_get_projects", "列出当前身份可以查看的 Jira 项目。", _schema({}, []),
          lambda a: t_get_projects(), READ_ONLY),
    _tool(
        "jira_search_issues",
        "按 JQL 搜索 Jira。查询本人负责可使用 assignee = currentUser()。",
        _schema({
            "jql": {"type": "string", "description": "Jira JQL 查询语句"},
            "max_results": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
        }, ["jql"]),
        lambda a: t_search_issues(a["jql"], a.get("max_results", 20)), READ_ONLY,
    ),
    _tool(
        "jira_get_issue",
        "读取 Jira 详情，包括描述、最近评论、常用字段、自定义字段和真实链接。",
        _schema({
            "issue_key": {"type": "string", "description": "Jira 编号，例如 PROJ-123"},
            "comment_limit": {"type": "integer", "default": 10, "minimum": 0, "maximum": 50},
            "include_custom_fields": {"type": "boolean", "default": True},
        }, ["issue_key"]),
        lambda a: t_get_issue(
            a["issue_key"], a.get("comment_limit", 10), a.get("include_custom_fields", True)
        ), READ_ONLY,
    ),
    _tool(
        "jira_get_create_fields",
        "查询指定项目和问题类型可填写的字段、必填项及枚举值。创建前必须先查询。",
        _schema({"project": S, "issue_type": S}, ["project", "issue_type"]),
        lambda a: t_get_create_fields(a["project"], a["issue_type"]), READ_ONLY,
    ),
    _tool(
        "jira_prepare_issue",
        "只读预检创建内容，返回最终字段和缺失必填项；不会创建 Jira。",
        _schema({
            "project": S, "issue_type": S, "summary": S, "description": S,
            "assignee": S, "priority": S, "labels": STRING_LIST,
            "components": STRING_LIST, "extra_fields": EXTRA_FIELDS,
        }, ["project", "issue_type", "summary"]),
        lambda a: t_prepare_issue(
            a["project"], a["issue_type"], a["summary"], a.get("description", ""),
            a.get("assignee"), a.get("priority"), a.get("labels"),
            a.get("components"), a.get("extra_fields"),
        ), READ_ONLY,
    ),
    _tool(
        "jira_create_issue",
        "创建 Jira。调用前必须完成预检并获得用户确认；写入后自动回读验证。",
        _schema({
            "project": S, "issue_type": S, "summary": S, "description": S,
            "assignee": S, "priority": S, "labels": STRING_LIST,
            "components": STRING_LIST, "extra_fields": EXTRA_FIELDS,
        }, ["project", "issue_type", "summary"]),
        lambda a: t_create_issue(
            a["project"], a["issue_type"], a["summary"], a.get("description", ""),
            a.get("assignee"), a.get("priority"), a.get("labels"),
            a.get("components"), a.get("extra_fields"),
        ), WRITE_CREATE,
    ),
    _tool(
        "jira_get_edit_fields",
        "查询一张 Jira 当前允许编辑的字段、字段类型和枚举值。修改自定义字段前先查询。",
        _schema({"issue_key": S}, ["issue_key"]),
        lambda a: t_get_edit_fields(a["issue_key"]), READ_ONLY,
    ),
    _tool(
        "jira_update_issue",
        "修改 Jira 字段。执行前必须展示变更并获得用户确认；写入后自动回读验证。",
        _schema({
            "issue_key": S, "summary": S, "description": S, "priority": S,
            "labels": STRING_LIST, "extra_fields": EXTRA_FIELDS,
        }, ["issue_key"]),
        lambda a: t_update_issue(
            a["issue_key"], a.get("summary"), a.get("description"),
            a.get("priority"), a.get("labels"), a.get("extra_fields"),
        ), WRITE_UPDATE,
    ),
    _tool(
        "jira_add_comment", "给 Jira 添加评论。执行前必须获得用户确认。",
        _schema({"issue_key": S, "comment": S}, ["issue_key", "comment"]),
        lambda a: t_add_comment(a["issue_key"], a["comment"]), WRITE_CREATE,
    ),
    _tool(
        "jira_get_transitions", "查询当前工作流实际允许执行的状态流转。",
        _schema({"issue_key": S}, ["issue_key"]),
        lambda a: t_get_transitions(a["issue_key"]), READ_ONLY,
    ),
    _tool(
        "jira_transition_issue",
        "执行状态流转，可传流转名称、目标状态或 ID。执行前必须查询可用流转并获得用户确认。",
        _schema({"issue_key": S, "transition": S, "comment": S}, ["issue_key", "transition"]),
        lambda a: t_transition_issue(a["issue_key"], a["transition"], a.get("comment")),
        WRITE_UPDATE,
    ),
    _tool(
        "jira_assign_issue", "修改 Jira 负责人。执行前必须获得用户确认。",
        _schema({"issue_key": S, "assignee": S}, ["issue_key", "assignee"]),
        lambda a: t_assign_issue(a["issue_key"], a["assignee"]), WRITE_UPDATE,
    ),
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
        protocol_ver = client_ver if client_ver in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": protocol_ver,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": SERVER_INSTRUCTIONS,
        }})
    elif method in ("notifications/initialized",) or (method is None and not is_request):
        pass
    elif method == "tools/list":
        _send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "tools": [{"name": t["name"], "description": t["description"],
                       "inputSchema": t["inputSchema"], "annotations": t["annotations"]}
                      for t in TOOLS]}})
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
