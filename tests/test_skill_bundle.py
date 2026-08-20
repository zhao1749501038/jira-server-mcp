import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "jira-mcp"


def load_skill_installer():
    path = SKILL / "scripts" / "install_mcp_macos.py"
    spec = importlib.util.spec_from_file_location("skill_mcp_installer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillBundleTests(unittest.TestCase):
    def test_skill_bundle_contains_required_files(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL / "scripts" / "install_mcp_macos.py").is_file())
        self.assertTrue((SKILL / "references" / "setup.md").is_file())

    def test_one_sentence_setup_prompts_credentials_in_gui(self):
        installer = load_skill_installer()
        command = installer.installer_command(
            Path("/tmp/install_codex_macos.py"),
            "https://jira.example",
            "jira",
        )
        self.assertIn("--gui", command)
        self.assertNotIn("--username", command)

if __name__ == "__main__":
    unittest.main()
