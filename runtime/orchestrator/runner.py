#!/usr/bin/env python3
"""Any-to-Any AI Orchestrator Runner for Respected Brain.

Enables dynamic Master-Worker pairing across any AI model:
  - Master: Plans and writes the specification (Claude, Gemini, Antigravity, Codex, Cursor, User).
  - Worker: Executes in an isolated Git worktree, runs tests, and produces a clean git patch.
The main working tree is NEVER modified directly by worker models.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SUPPORTED_AGENTS = ("claude", "gemini", "antigravity", "agy", "codex", "cursor", "user")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")[:40] or "task"


def get_cli_command(agent: str) -> list[str] | None:
    agent = agent.lower().strip()
    if agent in ("antigravity", "agy"):
        cmd = shutil.which("agy") or shutil.which("agy.exe") or shutil.which("agy.cmd")
        return [cmd] if cmd else None
    elif agent == "gemini":
        cmd = shutil.which("gemini") or shutil.which("gemini.exe") or shutil.which("gemini.cmd")
        return [cmd] if cmd else None
    elif agent == "claude":
        cmd = shutil.which("claude") or shutil.which("claude.exe") or shutil.which("claude.cmd")
        return [cmd] if cmd else None
    elif agent == "codex":
        cmd = shutil.which("codex") or shutil.which("codex.exe") or shutil.which("codex.cmd")
        return [cmd] if cmd else None
    elif agent == "cursor":
        cmd = shutil.which("cursor-agent") or shutil.which("cursor-agent.exe") or shutil.which("cursor-agent.cmd")
        return [cmd] if cmd else None
    return None


class OrchestrationRun:
    def __init__(
        self,
        task: str,
        master: str,
        worker: str,
        repo_root: Path,
        state_root: Path | None = None,
        test_command: str | None = None,
    ) -> None:
        self.task = task
        self.master = master.lower().strip()
        self.worker = worker.lower().strip()
        self.repo_root = repo_root.resolve()
        
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = slugify(task)
        self.run_id = f"run-{timestamp}-{slug}"

        self.state_root = (state_root or (self.repo_root.parent / ".orchestration-state")).resolve()
        self.run_dir = self.state_root / self.run_id
        self.worktrees_root = (self.repo_root.parent / f"{self.repo_root.name}-worktrees").resolve()
        self.worktree_dir = self.worktrees_root / self.run_id
        self.branch_name = f"worktree/{self.run_id}"
        self.test_command = test_command

    def _init_storage(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_root.mkdir(parents=True, exist_ok=True)

    def _write_metadata(self, status: str, **extra: object) -> None:
        data = {
            "run_id": self.run_id,
            "created_at": dt.datetime.now().isoformat(),
            "master": self.master,
            "worker": self.worker,
            "task": self.task,
            "status": status,
            "repo_root": str(self.repo_root),
            "worktree_path": str(self.worktree_dir),
            "branch_name": self.branch_name,
            **extra,
        }
        (self.run_dir / "metadata.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def setup_worktree(self) -> bool:
        self._init_storage()
        self._write_metadata(status="setting_up")

        # Get base commit hash
        base_commit_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if base_commit_proc.returncode != 0:
            print(f"[!] Hata: Git reposu doğrulanamadı ({self.repo_root})", file=sys.stderr)
            self._write_metadata(status="failed", error="Not a git repository or git rev-parse failed")
            return False

        base_commit = base_commit_proc.stdout.strip()
        (self.run_dir / "base_commit.txt").write_text(base_commit, encoding="utf-8")

        # Create isolated worktree
        print(f"[+] İzole Git worktree oluşturuluyor: {self.worktree_dir}")
        wt_cmd = [
            "git", "worktree", "add", "-b", self.branch_name,
            str(self.worktree_dir), "HEAD"
        ]
        proc = subprocess.run(wt_cmd, cwd=self.repo_root, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[!] Worktree oluşturulamadı: {proc.stderr}", file=sys.stderr)
            self._write_metadata(status="failed", error=proc.stderr)
            return False

        # Write task specification into worktree
        spec_content = (
            f"# GÖREV SPESİFİKASYONU: {self.task}\n\n"
            f"- Run ID: `{self.run_id}`\n"
            f"- Master Model: `{self.master}`\n"
            f"- Worker Model: `{self.worker}`\n"
            f"- Oluşturulma: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- Başlangıç Commiti: `{base_commit}`\n\n"
            f"## Talimatlar\n"
            f"1. Bu çalışma ağacı ana depodan tamamen izoledir.\n"
            f"2. Görevi tamamlamak için gerekli kod değişikliklerini yapın.\n"
            f"3. Değişiklikleriniz tamamlandığında testleri çalıştırın.\n"
            f"4. İşlem bittiğinde otomatik olarak yama (worker.patch) üretilecektir.\n"
        )
        (self.worktree_dir / "TASK_SPEC.md").write_text(spec_content, encoding="utf-8")
        return True

    def execute_worker(self) -> int:
        self._write_metadata(status="in_progress")
        log_file = self.run_dir / "worker.log"
        print(f"[*] İşçi çalıştırılıyor: Master={self.master} -> Worker={self.worker}")

        start_time = time.time()
        exit_code = 0

        if self.worker == "user":
            print(f"\n[?] Manuel kullanıcı modu.")
            print(f"Lütfen şu dizinde değişikliklerinizi yapın: {self.worktree_dir}")
            print("İşiniz bittiğinde Enter'a basarak devam edin...")
            input()
            exit_code = 0
        else:
            cli_cmd = get_cli_command(self.worker)
            if not cli_cmd:
                err_msg = f"Worker CLI '{self.worker}' sistemde bulunamadı."
                print(f"[!] {err_msg}", file=sys.stderr)
                log_file.write_text(err_msg, encoding="utf-8")
                self._write_metadata(status="failed", error=err_msg)
                return 1

            prompt = (
                f"Sen bir yazılım işçisisin. Görev: {self.task}\n"
                f"Lütfen TASK_SPEC.md dosyasını incele ve gerekli tüm kod değişikliklerini uygula. "
                f"İşin bittiğinde değişiklikleri kaydet."
            )

            # Build command depending on worker CLI
            if self.worker in ("antigravity", "agy"):
                full_cmd = cli_cmd + ["--prompt", prompt]
            elif self.worker == "gemini":
                full_cmd = cli_cmd + ["-p", prompt]
            elif self.worker == "claude":
                full_cmd = cli_cmd + ["-p", prompt]
            elif self.worker == "codex":
                full_cmd = cli_cmd + ["exec", prompt]
            else:
                full_cmd = cli_cmd + [prompt]

            with open(log_file, "w", encoding="utf-8", errors="replace") as f_out:
                proc = subprocess.run(
                    full_cmd,
                    cwd=self.worktree_dir,
                    stdout=f_out,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                exit_code = proc.returncode

        # Run optional verification tests
        test_passed = True
        test_output = ""
        if self.test_command:
            print(f"[*] Doğrulama testi koşturuluyor: {self.test_command}")
            t_proc = subprocess.run(
                self.test_command,
                shell=True,
                cwd=self.worktree_dir,
                capture_output=True,
                text=True,
            )
            test_passed = (t_proc.returncode == 0)
            test_output = t_proc.stdout + "\n" + t_proc.stderr
            (self.run_dir / "test_output.log").write_text(test_output, encoding="utf-8")
            if not test_passed:
                print(f"[!] Doğrulama testi BAŞARISIZ oldu (kod: {t_proc.returncode})", file=sys.stderr)

        duration = round(time.time() - start_time, 2)
        self.collect_patch(exit_code=exit_code, test_passed=test_passed, duration=duration)
        return exit_code

    def collect_patch(self, exit_code: int, test_passed: bool, duration: float) -> None:
        # Remove TASK_SPEC.md from untracked/staging if created
        task_spec = self.worktree_dir / "TASK_SPEC.md"
        if task_spec.is_file():
            task_spec.unlink()

        # Capture git status and diff
        diff_proc = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=self.worktree_dir,
            capture_output=True,
            text=True,
        )
        patch_text = diff_proc.stdout
        
        # If HEAD has not changed, also check unstaged or committed differences from base_commit
        base_commit_file = self.run_dir / "base_commit.txt"
        base_commit = base_commit_file.read_text(encoding="utf-8").strip() if base_commit_file.is_file() else "HEAD"
        if not patch_text.strip():
            diff_base_proc = subprocess.run(
                ["git", "diff", base_commit],
                cwd=self.worktree_dir,
                capture_output=True,
                text=True,
            )
            patch_text = diff_base_proc.stdout

        patch_file = self.run_dir / "worker.patch"
        patch_file.write_text(patch_text, encoding="utf-8")

        status_proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.worktree_dir,
            capture_output=True,
            text=True,
        )

        final_status = "completed" if (exit_code == 0 and test_passed and bool(patch_text.strip())) else (
            "empty" if not patch_text.strip() else "failed"
        )

        result_data = {
            "run_id": self.run_id,
            "status": final_status,
            "exit_code": exit_code,
            "test_passed": test_passed,
            "duration_seconds": duration,
            "has_patch": bool(patch_text.strip()),
            "patch_lines": len(patch_text.splitlines()),
            "files_modified": status_proc.stdout.strip().splitlines(),
        }
        (self.run_dir / "result.json").write_text(
            json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._write_metadata(
            status=final_status,
            duration_seconds=duration,
            patch_lines=len(patch_text.splitlines()),
            test_passed=test_passed,
        )

        print(f"[✓] Orkestrasyon tamamlandı: Durum={final_status}, Süre={duration}s, Yama={len(patch_text.splitlines())} satır")
        print(f"[👉] Dashboard üzerinden inceleyip onaylayabilirsiniz: http://localhost:8520")

    def cleanup_worktree(self) -> None:
        if self.worktree_dir.is_dir():
            print(f"[*] Worktree kaldırılıyor: {self.worktree_dir}")
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self.worktree_dir)],
                cwd=self.repo_root,
                capture_output=True,
            )
            subprocess.run(
                ["git", "branch", "-D", self.branch_name],
                cwd=self.repo_root,
                capture_output=True,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Any-to-Any AI Orchestrator for Respected Brain")
    parser.add_argument("--task", "-t", required=True, help="Yapılacak görev tanımı")
    parser.add_argument("--master", "-m", default="user", choices=SUPPORTED_AGENTS, help="Yönetici model (varsayılan: user)")
    parser.add_argument("--worker", "-w", default="antigravity", choices=SUPPORTED_AGENTS, help="İşçi model (varsayılan: antigravity)")
    parser.add_argument("--repo", "-r", type=Path, default=Path.cwd(), help="Hedef git reposu")
    parser.add_argument("--test", type=str, default=None, help="Koşturulacak doğrulama komutu (örn: 'pytest' veya 'python -m unittest')")
    parser.add_argument("--cleanup", action="store_true", help="İşlem bittiğinde worktree'yi temizle")

    args = parser.parse_args(argv)

    run = OrchestrationRun(
        task=args.task,
        master=args.master,
        worker=args.worker,
        repo_root=args.repo,
        test_command=args.test,
    )

    if not run.setup_worktree():
        return 1

    code = run.execute_worker()

    if args.cleanup:
        run.cleanup_worktree()

    return code


if __name__ == "__main__":
    sys.exit(main())
