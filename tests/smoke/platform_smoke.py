#!/usr/bin/env python3
"""Destructive-safe physical-host smoke test for Respected Brain 0.0.1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("antigravity", "gemini", "codex", "cursor", "claude")


def _configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console_output()


def _run(command: list[str], *, env: dict[str, str] | None = None) -> tuple[int, str, float]:
    started = time.perf_counter()
    merged = os.environ.copy()
    merged.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    if env:
        merged.update(env)
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    return process.returncode, (process.stdout + process.stderr)[-4000:], time.perf_counter() - started


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_uninstaller():
    spec = importlib.util.spec_from_file_location("smoke_uninstall", ROOT / "installer" / "uninstall.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("uninstall.py yüklenemedi")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON kanıt dosyası")
    parser.add_argument("--keep", action="store_true", help="geçici çalışma alanını koru")
    args = parser.parse_args(argv)

    is_wsl = bool(os.environ.get("WSL_DISTRO_NAME"))
    host = "windows-native" if os.name == "nt" else ("wsl" if is_wsl else "macos" if sys.platform == "darwin" else "linux")
    profile = "windows-native" if host == "windows-native" else "portable"
    root = Path(tempfile.mkdtemp(prefix="respected-physical-smoke-"))
    vault = root / "Furkan Smoke 🧠"
    home = root / "home"
    home.mkdir()
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: str = "", duration: float = 0.0) -> None:
        checks.append({
            "name": name,
            "status": "VERIFIED" if passed else "FAILED",
            "detail": detail[:500],
            "duration_seconds": round(duration, 3),
        })
        if not passed:
            raise RuntimeError(f"{name}: {detail}")

    try:
        install_command = [
            sys.executable, str(ROOT / "installer" / "install.py"), "--non-interactive",
            "--vault-path", str(vault), "--user-name", "Smoke User",
            "--os-name", "SmokeOS", "--provider", "auto",
            "--environment", "native", "--quiet",
        ]
        if os.name == "nt":
            install_command += ["--python-executable", sys.executable]
        code, output, elapsed = _run(install_command)
        passed = code == 0 and (vault / ".respectedbrain-version").is_file()
        record("transactional-fresh-install", passed, "" if passed else output, elapsed)

        code, output, elapsed = _run([
            sys.executable, str((ROOT / "runtime/scripts/install_global.py") if (ROOT / "runtime/scripts/install_global.py").is_file() else (ROOT / "scripts/install_global.py")), str(vault),
            "--home", str(home), "--platform", profile, "--providers", "all", "--apply",
        ])
        adapters = [
            home / ".gemini/config/hooks.json", home / ".gemini/settings.json",
            home / ".codex/config.toml", home / ".cursor/hooks.json",
            home / ".claude/settings.json",
        ]
        passed = code == 0 and all(path.is_file() for path in adapters)
        record("five-provider-global-install", passed, "" if passed else output, elapsed)

        helper = root / "summary_model.py"
        helper.write_text(
            "print('## Bağlam\\nSmoke bağlam\\n\\n## Önemli Konuşmalar\\nSmoke konuşma\\n\\n'"
            "+ '## Alınan Kararlar\\nSmoke karar\\n\\n## Öğrenilenler\\nSmoke öğrenim\\n\\n'"
            "+ '## Yapılacaklar\\n- Smoke tamamla')\n",
            encoding="utf-8",
        )
        state = (vault / ".beyin/engine/.state") if (vault / ".beyin/engine").is_dir() else (root / ".state")
        state.mkdir(parents=True, exist_ok=True)
        transcript = root / "synthetic-transcript.jsonl"
        env = {
            "HOME": str(home), "USERPROFILE": str(home), "BEYIN_PROVIDER": "codex",
            "BEYIN_LLM_COMMAND": f'"{Path(sys.executable).as_posix()}" "{helper.as_posix()}"',
        }
        flush = (vault / ".beyin/engine/flush.py") if (vault / ".beyin/engine/flush.py").is_file() else (ROOT / "runtime/engine/flush.py")
        total_elapsed = 0.0
        for revision in (1, 2):
            transcript.write_text(
                json.dumps({"role": "user", "content": f"synthetic turn {revision}"}) + "\n" +
                json.dumps({"role": "assistant", "content": "synthetic answer"}) + "\n",
                encoding="utf-8",
            )
            hook_input = state / f"hookin-smoke-{revision}.json"
            hook_input.write_text(json.dumps({
                "session_id": "physical-smoke-session",
                "transcript_path": str(transcript),
            }), encoding="utf-8")
            code, output, elapsed = _run([
                sys.executable, str(flush), "--hook-input", str(hook_input), "--reason", "turn",
                "--vault", str(vault),
            ], env=env)
            total_elapsed += elapsed
            record(f"turn-flush-revision-{revision}", code == 0, "" if code == 0 else output, elapsed)
        daily_files = list((vault / "daily").glob("*.md"))
        daily = daily_files[0] if len(daily_files) == 1 else Path()
        daily_text = daily.read_text(encoding="utf-8") if daily.is_file() else ""
        record(
            "same-session-atomic-upsert",
            daily.is_file()
            and daily_text.count("### Oturum") == 1
            and daily_text.count("<!-- RESPECTED-SESSION:") == 2
            and daily_text.count(":BEGIN -->") == 1
            and "Smoke bağlam" in daily_text,
            f"daily_files={len(daily_files)} total_flush_seconds={total_elapsed:.3f}",
        )
        daily_hash = _sha256(daily)

        for number in (1, 2):
            code, output, elapsed = _run([
                sys.executable, str(ROOT / "installer" / "update.py"), str(vault), "--apply", "--force",
                "--platform", profile,
            ], env={"HOME": str(home), "USERPROFILE": str(home)})
            record(f"transactional-update-{number}", code == 0, "" if code == 0 else output, elapsed)
        record("update-preserves-daily-byte-for-byte", _sha256(daily) == daily_hash)

        sentinel = home / "keep-user-file.txt"
        sentinel.write_text("keep", encoding="utf-8")
        uninstaller = _load_uninstaller()
        with mock.patch("pathlib.Path.home", return_value=home):
            uninstaller.remove_global_integrations(clean_wsl=False)
        codex_rule = home / ".codex/AGENTS.md"
        record(
            "managed-only-global-uninstall",
            sentinel.read_text(encoding="utf-8") == "keep"
            and (
                not codex_rule.exists()
                or "RESPECTED-GLOBAL" not in codex_rule.read_text(encoding="utf-8")
            ),
        )
    except Exception as error:
        if not checks or checks[-1]["status"] != "FAILED":
            checks.append({"name": "smoke-runner", "status": "FAILED", "detail": str(error), "duration_seconds": 0.0})

    report = {
        "schema_version": 1,
        "host": host,
        "profile": profile,
        "platform": platform.platform(),
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "wsl_distribution": os.environ.get("WSL_DISTRO_NAME"),
        "providers": list(PROVIDERS),
        "workspace": str(root) if args.keep else "deleted-after-run",
        "checks": checks,
        "overall": "VERIFIED" if checks and all(item["status"] == "VERIFIED" for item in checks) else "FAILED",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.expanduser().resolve().write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
    return 0 if report["overall"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
