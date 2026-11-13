import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


class PortableWorkstreamTest(unittest.TestCase):
    def test_relocated_runtime_generates_and_validates(self):
        package = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="orca portable ") as tmp:
            root = Path(tmp)
            skill = root / "installed skills" / "orca-prompt"
            shutil.copytree(package / "skills" / "orca-prompt", skill, ignore=shutil.ignore_patterns("__pycache__"))
            work = root / ".orca" / "prompts" / "demo"
            work.mkdir(parents=True)
            models = {key: None for key in ("mainOrchestrator", "orchestrationWorker", "subagent", "subagentSimple")}
            config = {"workstream": "demo", "targetBranch": "main", "integration": "branch", "tickets": False,
                      "harnesses": [{"name": "codex", "tier": "standard", "models": models}],
                      "mainOrchestratorHarness": "codex", "maxConcurrency": 2,
                      "workItems": [{"id": "01-build", "size": "standard"}]}
            (work / "_config.json").write_text(json.dumps(config))
            (work / "_plan.md").write_text("# Demo\n\n## Definition of Done\n\nTests pass.\n\n## Orchestration Rules\n\n## Work Items\n\n### 01-build: Build\n\nBuild it.\n\n**Definition of Done**: Tests pass.\n**Wave**: 1\n")
            env = dict(os.environ)
            env.pop("CLAUDE_PLUGIN_ROOT", None)
            for script in ("scaffold.py", "validate.py"):
                subprocess.run([sys.executable, str(skill / "scripts" / script), str(work)], check=True, env=env, capture_output=True, text=True)
            subprocess.run([sys.executable, str(skill / "scripts" / "set_status.py"), str(work), "--start"], check=True, env=env, capture_output=True, text=True)
            self.assertEqual(json.loads((work / "_status.json").read_text())["items"][0]["state"], "todo")
            prompt = (work / "_orchestration.prompt.md").read_text()
            self.assertIn(shlex.quote(str((skill / "scripts").resolve())) + "/dispatch.py", prompt)
            for absent in ("CLAUDE_PLUGIN_ROOT", "orca-kb", "grill-with-docs", "to-tickets"):
                self.assertNotIn(absent, prompt)


if __name__ == "__main__":
    unittest.main()
