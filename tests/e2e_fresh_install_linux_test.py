#!/usr/bin/env python3
"""Standalone source CLI registration and provider lifecycle E2E on Linux/POSIX."""

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
from respectedbrain.core.resources import ResourceCatalog
from respectedbrain.core.config import ConfigStore
from tests.foundation_support import make_context


class E2EFreshInstallLinuxTest(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.skipTest("Linux/POSIX source E2E; native package smoke is separate")

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
elif "{provider}" == "gemini":
    print(json.dumps({{"response": "## Bağlam\\nE2E bağlam\\n\\n## Önemli Konuşmalar\\nE2E konuşma\\n\\n## Alınan Kararlar\\nE2E karar\\n\\n## Öğrenilenler\\nE2E öğrenilen\\n\\n## Yapılacaklar\\n- E2E tamamla", "stats": {{}}, "error": None}}))
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
        """Materialize packaged notes and register them through the public source CLI."""
        vault = target_dir / "TestVault"
        with ResourceCatalog().materialize("vault-template") as template:
            shutil.copytree(template,vault)
        env = {**os.environ, "HOME": str(target_dir / "home"), "USERPROFILE": str(target_dir / "home"), "RESPECTED_APP_DIR": str(target_dir / "app"), "RESPECTED_DATA_DIR": str(target_dir / "data")}
        registered = subprocess.run([sys.executable, "-m", "respectedbrain", "vault", "register", str(vault)], cwd=target_dir, env=env, capture_output=True, text=True)
        self.assertEqual(registered.returncode, 0, registered.stderr)
        from respectedbrain.vault.registry import build_context
        from respectedbrain.core.paths import Roots
        store = ConfigStore(target_dir / "data")
        store.update(lambda doc: doc["preferences"].update(summary_provider=provider, provider_priority=[provider], provider_fallback=False))
        self.ctx = build_context(Roots(target_dir / "app", target_dir / "data", vault), store, vault=vault, vault_id=None, env={})
        self.assertFalse((vault / ".beyin").exists())
        return vault

    def test_standalone_source_lifecycle_for_all_providers(self):
        """Verify every provider can run flush and generate a daily entry."""
        providers = ("claude", "codex", "antigravity", "gemini", "cursor")

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
                    state_dir = self.ctx.paths.state_dir
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
                    env["RESPECTED_APP_DIR"] = str(self.ctx.paths.app_root)
                    env["RESPECTED_DATA_DIR"] = str(self.ctx.paths.data_root)

                    result = subprocess.run(
                        [sys.executable,"-m","respectedbrain","flush","--vault-id",self.ctx.paths.vault_id,"--hook-input",str(hook_input),"--reason","sessionend"],
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
