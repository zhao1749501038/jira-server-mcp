import tempfile
import unittest
from pathlib import Path

import install_codex_macos as installer


class InstallerTests(unittest.TestCase):
    def test_set_writes_approval_only_changes_target_server(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                '[mcp_servers.other]\ncommand = "other"\n\n'
                '[mcp_servers.jira]\ncommand = "python3"\n\n'
                '[mcp_servers.jira.env]\nJIRA_BASE_URL = "https://jira.example"\n',
                encoding="utf-8",
            )
            installer.set_writes_approval(config, "jira")
            result = config.read_text(encoding="utf-8")
            self.assertIn(
                '[mcp_servers.jira]\n'
                'default_tools_approval_mode = "writes"\n',
                result,
            )
            self.assertNotIn(
                '[mcp_servers.other]\n'
                'default_tools_approval_mode = "writes"',
                result,
            )


if __name__ == "__main__":
    unittest.main()
