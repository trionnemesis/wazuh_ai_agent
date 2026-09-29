"""Offline regression for the README's full-lab Compose configuration.

Run from the repository root: python -m unittest discover -s tests -v
Requires Docker Compose; no Docker daemon, image pull or real credentials needed.
Set COMPOSE_COMMAND to a standalone Compose binary when Docker CLI is absent.
"""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SINGLE_NODE = ROOT / "wazuh-docker" / "single-node"


class ComposeConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "single-node"
        self.project.mkdir()
        # Copy only source configuration, never a developer's .env or certificates.
        for name in ("docker-compose.yml", "docker-compose.override.yml"):
            shutil.copyfile(SINGLE_NODE / name, self.project / name)
        agent = self.project / "ai-agent-project"
        agent.mkdir()
        shutil.copyfile(SINGLE_NODE / "ai-agent-project" / "Dockerfile", agent / "Dockerfile")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        block = re.search(r"cat > (ai-agent-project/\.env) << '?EOF'?\n(.*?)\nEOF", readme, re.S)
        self.assertIsNotNone(block, "README must define the environment file used by Quick Start")
        # The example's synthetic placeholder values are sufficient for config resolution.
        (self.project / block[1]).write_text(block[2] + "\n", encoding="utf-8")

    def config(self, *files):
        command = shlex.split(os.environ.get("COMPOSE_COMMAND", "docker compose"))
        command += ["--project-name", "readme-contract"]
        for name in files:
            command += ["-f", name]
        command += ["config", "--format", "json"]
        result = subprocess.run(
            command, cwd=self.project, check=False, capture_output=True, text=True,
            timeout=30, env={"PATH": os.environ.get("PATH", "")},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_readme_env_file_reaches_the_agent(self):
        # No -f: exercise Compose's default base + override discovery, as in README.
        agent = self.config()["services"]["ai-agent"]
        self.assertEqual(agent["environment"]["LLM_PROVIDER"], "anthropic")
        self.assertEqual(agent["environment"]["ANTHROPIC_API_KEY"], "your_anthropic_api_key_here")
        self.assertEqual(agent["environment"]["OPENSEARCH_URL"], "https://wazuh.indexer:9200")
        self.assertEqual(Path(agent["build"]["context"]), self.project / "ai-agent-project")
        self.assertTrue((Path(agent["build"]["context"]) / agent["build"]["dockerfile"]).is_file())

    def test_full_lab_uses_a_managed_project_network(self):
        config = self.config()
        network = config["networks"]["default"]
        self.assertFalse(network.get("external", False))
        self.assertEqual(network["name"], "readme-contract_default")
        for service in config["services"].values():
            self.assertIn("default", service["networks"])
        self.assertIn("wazuh.indexer", config["services"]["ai-agent"]["depends_on"])

    def test_agent_api_is_published_on_loopback_only(self):
        ports = self.config()["services"]["ai-agent"].get("ports", [])
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["host_ip"], "127.0.0.1")
        self.assertEqual(str(ports[0]["published"]), "8000")
        self.assertEqual(ports[0]["target"], 8000)
        self.assertEqual(ports[0]["protocol"], "tcp")

    def test_override_preserves_all_wazuh_service_configuration(self):
        base = self.config("docker-compose.yml")
        combined = self.config()
        self.assertEqual(set(combined["services"]), set(base["services"]) | {"ai-agent"})
        for name, service in base["services"].items():
            self.assertEqual(combined["services"][name], service, name)
        self.assertEqual(combined["volumes"], base["volumes"])


if __name__ == "__main__":
    unittest.main()
