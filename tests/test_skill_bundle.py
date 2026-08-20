import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "jira-mcp"


class SkillBundleTests(unittest.TestCase):
    def test_skill_bundle_contains_required_files(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL / "scripts" / "install_mcp_macos.py").is_file())
        self.assertTrue((SKILL / "references" / "setup.md").is_file())

if __name__ == "__main__":
    unittest.main()
