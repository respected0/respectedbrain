#!/usr/bin/env python3
"""Provider-neutral fresh-install and lifecycle E2E tests for Linux/POSIX (Faz 2)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template"


class E2EFreshInstallLinuxTest(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            # On Windows, skip or run via WSL/POSIX emulation
            pass

    def _create_provider_stub(self, bin_dir: Path, provider: str) -> Path:
        bin_dir.mkdir(parents=True, exist_ok=True)
        script_name = "agy" if provider == "antigravity" else ("cursor-agent" if provider == "cursor" else provider)
        stub_path = bin_dir / script_name
        code = f"""#!/usr/bin/env python3
import sys, json, os

args = sys.argv[1:]
if "{provider}" in ("antigravity", "agy"):
    # Output stream-json format as expected by model_runner
    print(json.dumps({{"event": "result", "result": {{"status": "OK", "response": "## Bağlam\\nE2E bağlam\\n\\n## Önemli Konuşmalar\\nE2E konuşma\\n\\n## Alınan Kararlar\\nE2E karar\\n\\n## Öğrenilenler\\nE2E öğrenilen\\n\\n## Yapılacaklar\\n- E2E tamamla"}}}}))
else:
    print("## Bağlam\\nE2E bağlam\\n\\n## Önemli Konuşmalar\\nE2E konuşma\\n\\n## Alınan Kararlar\\nE2E karar\\n\\n## Öğrenilenler\\nE2E öğrenilen\\n\\n## Yapılacaklar\\n- E2E tamamla")
sys.exit(0)
"""
        stub_path.write_text(code, encoding="utf-8")
        stub_path.chmod(0o755)
        if os.name == "nt":
            cmd_path = bin_dir / f"{script_name}.cmd"
            cmd_path.write_text(f'@echo off\npython "{stub_path}" %*\n', encoding="utf-8")
        return stub_path

    def _setup_fresh_vault(self, target_dir: Path, provider: str) -> Path:
        """Create a fresh vault from template and render integrations."""
        vault = target_dir / "TestVault"
        shutil.copytree(TEMPLATE, vault)
        (vault / "daily").mkdir(exist_ok=True)
        (vault / "knowledge").mkdir(exist_ok=True)
        (vault / "knowledge" / "index.md").write_text("# Knowledge Index\n", encoding="utf-8")

        config = {
            "summary_provider": provider,
            "platform": "portable" if os.name != "nt" else "windows-native",
        }
        (vault / ".beyin" / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        # Run render_integrations
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_integrations.py")],
            cwd=vault,
            check=True,
            capture_output=True,
        )
        return vault

    def test_fresh_install_lifecycle_for_all_providers(self):
        """Verify that all 4 providers can run flush and generate daily entries in a fresh vault."""
        providers = ("claude", "codex", "antigravity", "cursor")

        for provider in providers:
            with self.subTest(provider=provider):
                with tempfile.TemporaryDirectory() as temp_dir:
                    sandbox = Path(temp_dir).resolve()
                    home_dir = sandbox / "home"
                    home_dir.mkdir()
                    bin_dir = sandbox / "bin"
                    self._create_provider_stub(bin_dir, provider)

                    vault = self._setup_fresh_vault(sandbox, provider)

                    # Prepare hook input
                    state_dir = vault / ".beyin" / "engine" / ".state"
                    state_dir.mkdir(parents=True, exist_ok=True)
                    transcript = vault / "transcript.jsonl"
                    transcript.write_text(
                        '{"role": "user", "content": "E2E fresh install test"}\n'
                        '{"role": "assistant", "content": "Tamamlandı"}\n',
                        encoding="utf-8",
                    )
                    hook_input = state_dir / f"hookin-{provider}.json"
                    hook_input.write_text(
                        json.dumps({
                            "session_id": f"e2e-session-{provider}",
                            "transcript_path": str(transcript),
                        }),
                        encoding="utf-8",
                    )

                    env = os.environ.copy()
                    env["HOME"] = str(home_dir)
                    env["USERPROFILE"] = str(home_dir)
                    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
                    env["BEYIN_PROVIDER"] = provider

                    flush_script = vault / ".beyin" / "engine" / "flush.py"
                    result = subprocess.run(
                        [sys.executable, str(flush_script), "--hook-input", str(hook_input), "--reason", "sessionend"],
                        cwd=vault,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        f"Flush failed for {provider}: {result.stderr}\n{result.stdout}",
                    )

                    # Assert daily note was created
                    daily_files = list((vault / "daily").glob("*.md"))
                    self.assertEqual(len(daily_files), 1, f"Expected 1 daily note for {provider}")
                    content = daily_files[0].read_text(encoding="utf-8")
                    self.assertIn("## Bağlam", content)
                    self.assertIn("E2E bağlam", content)


if __name__ == "__main__":
    unittest.main()
