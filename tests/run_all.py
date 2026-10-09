#!/usr/bin/env python3
"""Unified test orchestrator for Respected Brain.

Runs Python unit & integration tests, native PowerShell tests (on Windows),
and Bash tests (if bash is available), providing a single Golden Standard report.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
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


def run_command(title: str, command: list[str], env: dict | None = None, *, full_output: bool = False) -> tuple[bool, float, str]:
    print(f"\n>> Koşturuluyor: {title}", flush=True)
    start = time.perf_counter()
    merged_env = os.environ.copy()
    merged_env["PYTHONUTF8"] = "1"
    merged_env["PYTHONIOENCODING"] = "utf-8"
    merged_env["RESPECTED_TEST_PYTHON"] = sys.executable
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
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    elapsed = time.perf_counter() - start
    output = (process.stdout + process.stderr).strip()
    success = process.returncode == 0
    if success:
        print(f"   [PASS] {title} ({elapsed:.2f}s)", flush=True)
    else:
        print(f"   [FAIL] {title} ({elapsed:.2f}s) - Exit code: {process.returncode}", flush=True)
        if output and not full_output:
            print("   --- Çıktı ---", flush=True)
            for line in output.splitlines()[-15:]:
                print(f"   | {line}", flush=True)
            print("   -------------", flush=True)
    if full_output:
        sys.stdout.write(process.stdout)
        sys.stdout.flush()
        sys.stderr.write(process.stderr)
        sys.stderr.flush()
    return success, elapsed, output


def failed_test_ids(output: str) -> list[str]:
    """Extract public unittest identifiers; discard messages and subtest values."""
    identifier = r"[A-Za-z_][A-Za-z0-9_]*"
    header = re.compile(rf"^(?:FAIL|ERROR|UNEXPECTED SUCCESS): ({identifier}) \(((?:{identifier}\.)+{identifier})\)(?: .*)?$", re.MULTILINE)
    identities = []
    for method, identity in header.findall(output):
        last = identity.rsplit('.', 1)[-1]
        if last == method:
            identities.append(identity)
        elif re.fullmatch(r"_*[A-Z][A-Za-z0-9_]*", last):
            # Python 3.10 prints module.Class, later versions add .method.
            # Restrict the legacy form to public project class identifiers.
            identities.append(identity + "." + method)
    return list(dict.fromkeys(identities))


def run_python_tests() -> tuple[bool, float, str]:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "*test*.py"]
    success, elapsed, output = run_command("Python Birim ve Entegrasyon Testleri", command, full_output=True)
    if not success and os.environ.get("GITHUB_ACTIONS") == "true":
        identities = failed_test_ids(output)
        if identities:
            # GitHub limits error annotations per step; publish one safe list.
            labels = " ".join(f"test={identity}" for identity in identities)
            print(f"::error title=Python unittest failure::{labels}", flush=True)
    return success, elapsed, output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-only", action="store_true", help="Run Python discovery only; native payload is validated by the caller.")
    args = parser.parse_args(argv)
    if args.python_only:
        success, _, _ = run_python_tests()
        return 0 if success else 1

    print("=== Respected Brain Kalite ve Test Orkestratörü ===")
    print(f"Kök Dizin: {ROOT}")
    print(f"İşletim Sistemi: {os.name} ({sys.platform})")
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")

    results: list[tuple[str, str, bool, float]] = []
    capabilities = {
        "Windows Native fiziksel host": "NOT VERIFIED",
        "Saf WSL fiziksel host": "NOT VERIFIED",
        "Hibrit Windows+WSL fiziksel host": "NOT VERIFIED",
        "Saf Linux fiziksel host": "NOT VERIFIED",
        "macOS fiziksel host": "NOT VERIFIED",
    }

    platform = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    distribution = ROOT / "dist" / ("RespectedBrain.app" if platform == "macos" else "RespectedBrain")
    ok, elapsed, _ = run_command("Required Native Distribution", [sys.executable, "tools/verify_distribution.py", "--distribution", str(distribution), "--platform", platform])
    results.append(("Native distribution", "Frozen/no system Python", ok, elapsed))
    if not ok:
        print("Native payload is required before full-suite discovery; build tools/build_installer.py first.")
        return 1

    # 1. Python Test Paketi
    ok, elapsed, python_output = run_python_tests()
    count_match = re.search(r"Ran (\d+) tests?", python_output)
    count = count_match.group(1) if count_match else "?"
    results.append((f"Python Test Suite ({count} test)", "Birim & Entegrasyon", ok, elapsed))

    cmd = [sys.executable, "tests/smoke/platform_smoke.py", "--fixture-provenance"]
    ok, elapsed, _ = run_command("Fiziksel Host Platform Smoke", cmd)
    results.append(("platform_smoke.py", "Install/Turn/Update/Uninstall", ok, elapsed))
    physical_smoke_ok = ok

    # 2. Windows Native PowerShell Testleri
    if os.name == "nt":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if pwsh:
            cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/install_windows_test.ps1"]
            ok, elapsed, _ = run_command("PowerShell Kurulum Sözleşmesi", cmd, env={"PYTHONIOENCODING": "utf-8"})
            results.append(("PowerShell install_windows_test.ps1", "Windows Installer", ok, elapsed))
            native_ok = physical_smoke_ok and ok

            cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/windows_launchers_test.ps1"]
            ok, elapsed, _ = run_command("PowerShell Launcher Sözleşmesi", cmd, env={"PYTHONIOENCODING": "utf-8"})
            results.append(("PowerShell windows_launchers_test.ps1", "Windows Launchers", ok, elapsed))
            native_ok = native_ok and ok

            cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/briefing_schedule_windows_test.ps1"]
            ok, elapsed, _ = run_command("PowerShell Zamanlayıcı Sözleşmesi", cmd, env={"PYTHONIOENCODING": "utf-8"})
            results.append(("PowerShell briefing_schedule_windows_test.ps1", "Task Scheduler", ok, elapsed))
            native_ok = native_ok and ok
            if native_ok:
                capabilities["Windows Native fiziksel host"] = "VERIFIED"

            wsl = shutil.which("wsl.exe") or shutil.which("wsl")
            if wsl and os.environ.get("RESPECTED_WSL_PACKAGE"):
                cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tests/hybrid_wsl_smoke.ps1", "-LinuxPackage", os.environ["RESPECTED_WSL_PACKAGE"]]
                ok, elapsed, _ = run_command("Hibrit Windows+WSL Uçtan Uca Smoke", cmd)
                results.append(("PowerShell hybrid_wsl_smoke.ps1", "Hybrid Turn Flush", ok, elapsed))
                if ok:
                    capabilities["Hibrit Windows+WSL fiziksel host"] = "VERIFIED"
        else:
            print("\n>> UYARI: Required native PowerShell acceptance unavailable.")
            results.append(("PowerShell acceptance", "Required Windows gate", False, 0))

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

    if sys.platform.startswith("linux") and physical_smoke_ok:
        if os.environ.get("WSL_DISTRO_NAME"):
            capabilities["Saf WSL fiziksel host"] = "VERIFIED"
        else:
            capabilities["Saf Linux fiziksel host"] = "VERIFIED"
    elif sys.platform == "darwin" and physical_smoke_ok:
        capabilities["macOS fiziksel host"] = "VERIFIED"

    # Özet Rapor Tablosu
    print("\n" + "=" * 70)
    print("KALİTE VE DOĞRULAMA ÖZET RAPORU (Golden Standard)")
    print("=" * 70)

    print("\nFİZİKSEL HOST KANIT DURUMU")
    for capability, status in capabilities.items():
        print(f"- {capability}: {status}")
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
        print("\nGENEL SONUÇ: BU HOSTTA ÇALIŞTIRILABİLEN TÜM GATE'LER GEÇTİ.")
        print("NOT VERIFIED satırları harici fiziksel smoke yapılmadan PASS sayılmaz.\n")
        return 0
    else:
        print("GENEL SONUÇ: BAZI TESTLER BAŞARISIZ OLDU!\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
