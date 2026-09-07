#!/usr/bin/env python3
"""Unified test orchestrator for Respected Brain.

Runs Python unit & integration tests, native PowerShell tests (on Windows),
and Bash tests (if bash is available), providing a single Golden Standard report.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def _configure_console_output() -> None:
    """Keep Windows OEM consoles from aborting on emoji / unicode characters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console_output()

ROOT = Path(__file__).resolve().parents[1]


def run_command(title: str, command: list[str], env: dict | None = None) -> tuple[bool, float, str]:
    print(f"\n>> Koşturuluyor: {title}", flush=True)
    start = time.perf_counter()
    merged_env = os.environ.copy()
    merged_env["PYTHONUTF8"] = "1"
    merged_env["PYTHONIOENCODING"] = "utf-8"
    if env:
        merged_env.update(env)
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - start
    output = (process.stdout + process.stderr).strip()
    success = process.returncode == 0
    if success:
        print(f"   [PASS] {title} ({elapsed:.2f}s)", flush=True)
    else:
        print(f"   [FAIL] {title} ({elapsed:.2f}s) - Exit code: {process.returncode}", flush=True)
        if output:
            print("   --- Çıktı ---", flush=True)
            for line in output.splitlines()[-15:]:
                print(f"   | {line}", flush=True)
            print("   -------------", flush=True)
    return success, elapsed, output


def main() -> int:
    print("=== Respected Brain Kalite ve Test Orkestratörü ===")
    print(f"Kök Dizin: {ROOT}")
    print(f"İşletim Sistemi: {os.name} ({sys.platform})")
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")

    results: list[tuple[str, str, bool, float]] = []

    # 1. Python Test Paketi
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "*test*.py"]
    ok, elapsed, _ = run_command("Python Birim ve Entegrasyon Testleri", cmd)
    results.append(("Python Test Suite (*test*.py)", "Birim & Entegrasyon", ok, elapsed))

    # 2. Windows Native PowerShell Testleri
    if os.name == "nt":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if pwsh:
            cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/install_windows_test.ps1"]
            ok, elapsed, _ = run_command("PowerShell Kurulum Sözleşmesi", cmd, env={"PYTHONIOENCODING": "utf-8"})
            results.append(("PowerShell install_windows_test.ps1", "Windows Installer", ok, elapsed))

            cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/briefing_schedule_windows_test.ps1"]
            ok, elapsed, _ = run_command("PowerShell Zamanlayıcı Sözleşmesi", cmd, env={"PYTHONIOENCODING": "utf-8"})
            results.append(("PowerShell briefing_schedule_windows_test.ps1", "Task Scheduler", ok, elapsed))
        else:
            print("\n>> UYARI: PowerShell bulunamadı, Windows testleri atlandı.")

    # 3. Shell / Bash Testleri
    bash = shutil.which("bash")
    if bash:
        cmd = [bash, "tests/hooks_test.sh"]
        ok, elapsed, _ = run_command("Bash Hooks Test Paketi", cmd)
        results.append(("Bash hooks_test.sh", "Shell Hooks & Lifecycle", ok, elapsed))

        cmd = [bash, "tests/upstream_sync_test.sh"]
        ok, elapsed, _ = run_command("Bash Upstream Sync Test Paketi", cmd)
        results.append(("Bash upstream_sync_test.sh", "Git Sync Sözleşmesi", ok, elapsed))
    else:
        print("\n>> BİLGİ: Bash bulunamadı (Windows saf ortam), .sh testleri atlandı.")

    # Özet Rapor Tablosu
    print("\n" + "=" * 70)
    print("KALİTE VE DOĞRULAMA ÖZET RAPORU (Golden Standard)")
    print("=" * 70)
    print(f"{'Test Paketi':<45} | {'Kapsam':<20} | {'Durum':<6} | {'Süre':<6}")
    print("-" * 70)
    all_passed = True
    for name, scope, success, el in results:
        status = "PASS" if success else "FAIL"
        if not success:
            all_passed = False
        print(f"{name:<45} | {scope:<20} | {status:<6} | {el:5.1f}s")
    print("=" * 70)

    if all_passed:
        print("GENEL SONUÇ: TÜM TESTLER BAŞARIYLA GEÇTİ (Golden Standard Sağlandı)\n")
        return 0
    else:
        print("GENEL SONUÇ: BAZI TESTLER BAŞARISIZ OLDU!\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
