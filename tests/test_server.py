import json
import unittest
from unittest.mock import patch

import jira_mcp_server as server


def issue(key="DEMO-1", status="待处理", assignee="test-user"):
    return {
        "key": key,
        "fields": {
            "summary": "测试需求",
            "status": {"name": status},
            "assignee": {"name": assignee, "displayName": "测试用户"},
            "priority": {"name": "Medium"},
            "updated": "2026-08-20T09:00:00.000+0800",
        },
    }


class JiraMcpTests(unittest.TestCase):
    def test_read_and_write_annotations_are_distinct(self):
        tools = server.TOOLS_BY_NAME
        self.assertTrue(tools["jira_get_issue"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["jira_create_issue"]["annotations"]["readOnlyHint"])
        self.assertTrue(tools["jira_update_issue"]["annotations"]["destructiveHint"])

    def test_issue_key_validation(self):
        self.assertEqual(server._issue_key("demo-123"), "DEMO-123")
        with self.assertRaises(server.JiraError):
            server._issue_key("../myself")

    @patch("jira_mcp_server._request")
    def test_prepare_issue_reports_missing_required_fields(self, request):
        request.side_effect = [
            {"values": [{"id": "10110", "name": "业务需求"}]},
            {"values": [
                {"fieldId": "project", "name": "项目", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "issuetype", "name": "问题类型", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "summary", "name": "概要", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "components", "name": "模块", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "reporter", "name": "报告人", "required": True,
                 "hasDefaultValue": False},
            ]},
            {"name": "test-user"},
        ]
        result = json.loads(server.t_prepare_issue("DEMO", "业务需求", "标题"))
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing_required_fields"], [
            {"id": "components", "name": "模块"}
        ])
        self.assertEqual(result["fields"]["reporter"], {"name": "test-user"})

    @patch("jira_mcp_server._request")
    def test_transition_accepts_target_status_and_reads_back(self, request):
        request.side_effect = [
            {"transitions": [{"id": "31", "name": "开始设计", "to": {"name": "设计ing"}}]},
            {},
            issue(status="设计ing"),
        ]
        result = json.loads(server.t_transition_issue("DEMO-1", "设计ing"))
        self.assertEqual(result["target_status"], "设计ing")
        self.assertEqual(result["verified_issue"]["status"], "设计ing")
        self.assertEqual(request.call_args_list[1].args[0], "POST")

    @patch("jira_mcp_server._request")
    def test_update_supports_extra_fields_and_reads_back(self, request):
        request.side_effect = [{}, issue()]
        result = json.loads(server.t_update_issue(
            "DEMO-1", extra_fields={"customfield_10000": {"value": "已确认"}}
        ))
        body = request.call_args_list[0].kwargs["body"]
        self.assertEqual(body["fields"]["customfield_10000"], {"value": "已确认"})
        self.assertEqual(result["verified_issue"]["key"], "DEMO-1")

    @patch("jira_mcp_server._request")
    def test_create_checks_fields_and_reads_back(self, request):
        request.side_effect = [
            {"values": [{"id": "10110", "name": "业务需求"}]},
            {"values": [
                {"fieldId": "project", "name": "项目", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "issuetype", "name": "问题类型", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "summary", "name": "概要", "required": True,
                 "hasDefaultValue": False},
                {"fieldId": "components", "name": "模块", "required": True,
                 "hasDefaultValue": False},
            ]},
            {"key": "DEMO-2"},
            issue(key="DEMO-2"),
        ]
        result = json.loads(server.t_create_issue(
            "DEMO", "业务需求", "标题", components=["培训管理"]
        ))
        body = request.call_args_list[2].kwargs["body"]
        self.assertEqual(body["fields"]["components"], [{"name": "培训管理"}])
        self.assertEqual(request.call_args_list[3].kwargs["params"]["fields"], "*all")
        self.assertEqual(result["verified_issue"]["key"], "DEMO-2")


if __name__ == "__main__":
    unittest.main()
