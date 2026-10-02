#!/usr/bin/env python3
"""Respected Brain Local Gateway & Web Dashboard Server.

Runs a zero-dependency local control plane on http://localhost:8520.
Features:
  - Model Router & CLI Health (Claude, Gemini, Antigravity, Codex)
  - Memory & Health Monitor (Last-Session, Threads, Briefings, Compile Status)
  - Any-to-Any Orchestration Worktree & Diff Visualizer
  - Fast Full-Text Search (SQLite FTS5) & Note Viewer
  - Kasa Doktoru & Automated Actions
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
BEYIN_DIR = SCRIPT_DIR.parent
VAULT_ROOT = BEYIN_DIR.parent
STATIC_DIR = SCRIPT_DIR / "web"

if str(BEYIN_DIR) not in sys.path:
    sys.path.insert(0, str(BEYIN_DIR))

# Ensure secondbrain root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPTS_DIR = VAULT_ROOT / "scripts"
if SCRIPTS_DIR.is_dir() and str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
elif (REPO_ROOT / "runtime" / "scripts").is_dir() and str(REPO_ROOT / "runtime" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "runtime" / "scripts"))
elif (REPO_ROOT / "scripts").is_dir() and str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    import runtime_platform
except ImportError:
    runtime_platform = None  # type: ignore

# Global cache for CLI discovery to ensure sub-millisecond response times
_CLI_CACHE: dict[str, any] = {"ts": 0.0, "data": {}}


def _find_executable(cmd: str) -> str | None:
    found = shutil.which(cmd) or shutil.which(f"{cmd}.exe") or shutil.which(f"{cmd}.cmd") or shutil.which(f"{cmd}.bat")
    if found:
        return found
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        if cmd == "codex":
            codex_bin = Path(local_app) / "OpenAI" / "Codex" / "bin"
            if codex_bin.is_dir():
                for exe in codex_bin.glob("**/codex.exe"):
                    if exe.is_file():
                        return str(exe)
        elif cmd in ("agy", "antigravity"):
            agy_bin = Path(local_app) / "agy" / "bin" / "agy.exe"
            if agy_bin.is_file():
                return str(agy_bin)
    return None


def _get_cli_status(force_refresh: bool = False) -> dict[str, dict[str, str | bool | None]]:
    now = time.time()
    if not force_refresh and _CLI_CACHE["data"] and (now - _CLI_CACHE["ts"] < 45.0):
        return _CLI_CACHE["data"]

    tools = {
        "codex": {"cmd": "codex", "name": "OpenAI Codex"},
        "antigravity": {"cmd": "agy", "name": "Google Antigravity"},
        "gemini": {"cmd": "gemini", "name": "Google Gemini"},
        "claude": {"cmd": "claude", "name": "Anthropic Claude"},
        "cursor": {"cmd": "cursor-agent", "name": "Cursor Agent"},
    }
    status = {}
    for key, item in tools.items():
        executable = _find_executable(item["cmd"])
        version = None
        auth_status = "unknown"

        if executable:
            try:
                proc = subprocess.run(
                    [executable, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                    encoding="utf-8",
                    errors="replace",
                )
                output = (proc.stdout + " " + proc.stderr).strip()
                if output:
                    version = output.splitlines()[0][:60]
                if key == "claude" and ("not logged in" in output.lower() or "/login" in output.lower()):
                    auth_status = "not_logged_in"
                elif proc.returncode == 0:
                    auth_status = "ready"
                else:
                    auth_status = "error"
            except Exception:
                auth_status = "installed"
        else:
            auth_status = "missing"

        status[key] = {
            "name": item["name"],
            "installed": executable is not None,
            "path": executable,
            "version": version,
            "auth_status": auth_status,
        }

    _CLI_CACHE["ts"] = now
    _CLI_CACHE["data"] = status
    return status


def _read_file_safe(path: Path, max_chars: int = 50_000) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        pass
    return ""


def _read_json_safe(path: Path, default: dict | list) -> dict | list:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        pass
    return default


class DashboardHandler(BaseHTTPRequestHandler):
    vault_root: Path = VAULT_ROOT

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if os.environ.get("BEYIN_DASHBOARD_DEBUG"):
            super().log_message(format, *args)

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message, "success": False}, status=status)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        if path.startswith("/api/"):
            self._handle_api_get(path, params)
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self._send_error_json("Invalid JSON body")
            return

        if path == "/api/models/priority":
            self._handle_set_priority(payload)
        elif path == "/api/orchestration/start":
            self._handle_start_orchestration(payload)
        elif path == "/api/orchestration/apply":
            self._handle_apply_patch(payload)
        elif path == "/api/orchestration/reject":
            self._handle_reject_worktree(payload)
        elif path == "/api/actions/briefing":
            self._handle_run_briefing()
        elif path == "/api/actions/compile":
            self._handle_run_compile()
        elif path == "/api/actions/doctor":
            self._handle_run_doctor()
        elif path == "/api/actions/reindex":
            self._handle_run_reindex()
        elif path == "/api/actions/capture":
            self._handle_quick_capture(payload)
        else:
            self._send_error_json("Endpoint not found", 404)

    def _handle_api_get(self, path: str, params: dict[str, list[str]] | None = None) -> None:
        params = params or {}
        vault = self.vault_root
        state_dir = vault / ".beyin" / "engine" / ".state"
        config_path = vault / ".beyin" / "config.json"

        if path == "/api/status":
            config = _read_json_safe(config_path, {})
            version_file = vault / ".respectedbrain-version"
            version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "0.0.1"
            self._send_json({
                "vault_name": vault.name,
                "vault_path": str(vault),
                "version": version,
                "platform": config.get("platform", "windows-native"),
                "environment": config.get("environment", "native"),
                "summary_provider": config.get("summary_provider", "auto"),
            })

        elif path == "/api/models":
            force_refresh = bool(params.get("refresh", ["0"])[0] in ("1", "true"))
            config = _read_json_safe(config_path, {})
            cli_status = _get_cli_status(force_refresh=force_refresh)
            priority = list(config.get("provider_priority", ["codex", "antigravity", "gemini", "claude", "cursor"]))
            summary_provider = config.get("summary_provider", "auto")
            fallback = config.get("provider_fallback", True)

            # If summary_provider is explicitly set, ensure it is represented at index 0 of priority
            if summary_provider != "auto" and summary_provider in priority:
                priority.remove(summary_provider)
                priority.insert(0, summary_provider)

            self._send_json({
                "providers": cli_status,
                "priority": priority,
                "summary_provider": summary_provider,
                "fallback_enabled": fallback,
            })

        elif path == "/api/memory":
            companion = vault / "🔮 850-Companion"
            last_session = _read_file_safe(companion / "Last-Session.md")
            threads = _read_file_safe(companion / "Threads.md")
            kurallar = _read_file_safe(companion / "Kurallar.md")
            
            import datetime as dt
            today_str = dt.date.today().isoformat()
            daily_text = _read_file_safe(vault / "daily" / f"{today_str}.md")
            briefing_text = _read_file_safe(vault / "🎯 100-Command-Center" / "Briefings" / f"{today_str}.md")
            dashboard_text = _read_file_safe(vault / "🎯 100-Command-Center" / "Dashboard.md")

            self._send_json({
                "today": today_str,
                "last_session": last_session,
                "threads": threads,
                "kurallar": kurallar,
                "daily": daily_text,
                "briefing": briefing_text,
                "dashboard": dashboard_text,
            })

        elif path == "/api/health":
            health = _read_json_safe(state_dir / "health.json", {})
            briefing_health = _read_json_safe(state_dir / "briefing-health.json", {})
            compile_state = _read_json_safe(state_dir / "compile-state.json", {})
            last_flush = _read_json_safe(state_dir / "last-flush.json", {})

            self._send_json({
                "engine_health": health,
                "briefing_health": briefing_health,
                "compile_state": compile_state,
                "last_flush": last_flush,
            })

        elif path == "/api/orchestration":
            runs = []
            worktrees_root = vault.parent / f"{vault.name}-worktrees"
            
            state_candidates = [
                vault.parent / ".orchestration-state",
                vault / ".orchestration-state",
                REPO_ROOT.parent / ".orchestration-state",
                REPO_ROOT / ".orchestration-state",
            ]
            seen_runs = set()
            for s_root in state_candidates:
                if s_root.is_dir():
                    for run_dir in sorted(s_root.glob("run-*"), reverse=True)[:30]:
                        run_id = run_dir.name
                        if run_id in seen_runs:
                            continue
                        seen_runs.add(run_id)
                        meta = _read_json_safe(run_dir / "metadata.json", {})
                        patch = _read_file_safe(run_dir / "worker.patch", max_chars=60_000)
                        result = _read_json_safe(run_dir / "result.json", {})
                        runs.append({
                            "run_id": run_id,
                            "metadata": meta,
                            "result": result,
                            "has_patch": bool(patch.strip()),
                            "patch_preview": patch if patch else "",
                        })

            self._send_json({
                "worktrees_root": str(worktrees_root),
                "runs": runs,
            })

        elif path == "/api/search":
            q = params.get("q", [""])[0]
            limit = int(params.get("limit", ["15"])[0])
            category = params.get("category", [None])[0]
            try:
                import arama
                engine = arama.SearchEngine(vault)
                results = engine.search(q, limit=limit, category=category)
                self._send_json({"query": q, "results": results, "count": len(results)})
            except Exception as e:
                self._send_error_json(f"Search error: {e}")

        elif path == "/api/note":
            rel_path = params.get("path", [""])[0]
            if not rel_path:
                self._send_error_json("Missing path parameter")
                return
            safe_rel = rel_path.replace("\\", "/").strip("/").replace("..", "").strip()
            target_file = (self.vault_root / safe_rel).resolve()
            try:
                target_file.relative_to(self.vault_root.resolve())
            except ValueError:
                self._send_error_json("Access denied", 403)
                return
            if not target_file.is_file():
                self._send_error_json("Not bulunamadı", 404)
                return
            content = _read_file_safe(target_file, max_chars=120_000)
            stat = target_file.stat()
            import datetime as dt
            mtime = dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            self._send_json({
                "path": safe_rel,
                "title": target_file.stem,
                "content": content,
                "size": stat.st_size,
                "modified": mtime,
            })

        elif path == "/api/updater/check":
            version_file = vault / ".respectedbrain-version"
            current_ver = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "0.0.1"
            self._send_json({
                "current_version": current_ver,
                "latest_version": current_ver,
                "update_available": False,
                "status": "up_to_date",
            })

        else:
            self._send_error_json("API endpoint not found", 404)

    def _handle_set_priority(self, payload: dict) -> None:
        priority = payload.get("priority")
        summary_provider = payload.get("summary_provider")
        config_path = self.vault_root / ".beyin" / "config.json"
        config = _read_json_safe(config_path, {})

        if isinstance(priority, list):
            config["provider_priority"] = priority
            if config.get("summary_provider") not in ("auto", None) and priority:
                config["summary_provider"] = priority[0]

        if isinstance(summary_provider, str):
            config["summary_provider"] = summary_provider
            if summary_provider != "auto":
                curr_priority = list(config.get("provider_priority", ["codex", "antigravity", "gemini", "claude", "cursor"]))
                if summary_provider in curr_priority:
                    curr_priority.remove(summary_provider)
                curr_priority.insert(0, summary_provider)
                config["provider_priority"] = curr_priority

        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._send_json({
            "success": True,
            "config": config,
            "summary_provider": config.get("summary_provider", "auto"),
            "priority": config.get("provider_priority"),
        })

    def _handle_start_orchestration(self, payload: dict) -> None:
        task = payload.get("task", "").strip()
        master = payload.get("master", "user").strip()
        worker = payload.get("worker", "antigravity").strip()
        test_cmd = payload.get("test", None)

        if not task:
            self._send_error_json("Görev tanımı boş olamaz")
            return

        import threading
        try:
            from orchestrator.runner import OrchestrationRun
        except ImportError:
            sys.path.insert(0, str(self.vault_root / ".beyin"))
            from orchestrator.runner import OrchestrationRun

        target_repo = self.vault_root if (self.vault_root / ".git").is_dir() else REPO_ROOT
        run = OrchestrationRun(
            task=task,
            master=master,
            worker=worker,
            repo_root=target_repo,
            test_command=test_cmd,
        )

        if not run.setup_worktree():
            self._send_error_json("İzole worktree oluşturulamadı")
            return

        def _worker_bg():
            run.execute_worker()

        thread = threading.Thread(target=_worker_bg, daemon=True)
        thread.start()

        self._send_json({
            "success": True,
            "run_id": run.run_id,
            "message": f"Orkestrasyon başlatıldı ({master} -> {worker})",
            "worktree": str(run.worktree_dir),
        })

    def _handle_apply_patch(self, payload: dict) -> None:
        run_id = payload.get("run_id")
        if not run_id:
            self._send_error_json("Missing run_id")
            return

        patch_path = None
        target_repo = self.vault_root
        meta = {}
        for s_root in [
            self.vault_root.parent / ".orchestration-state",
            self.vault_root / ".orchestration-state",
            REPO_ROOT.parent / ".orchestration-state",
            REPO_ROOT / ".orchestration-state",
        ]:
            cand = s_root / run_id / "worker.patch"
            if cand.is_file():
                patch_path = cand
                meta = _read_json_safe(s_root / run_id / "metadata.json", {})
                break

        if not patch_path or not patch_path.is_file():
            self._send_error_json("Yama dosyası (worker.patch) bulunamadı", 404)
            return

        if meta.get("repo_root"):
            r = Path(meta["repo_root"])
            if r.is_dir() and (r / ".git").is_dir():
                target_repo = r

        cmd = ["git", "apply", "--whitespace=nowarn", str(patch_path)]
        res = subprocess.run(cmd, cwd=target_repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            self._send_json({"success": True, "message": f"{run_id} yamasını '{target_repo.name}' deposuna başarıyla uygulandı."})
        else:
            self._send_error_json(f"Git apply hatası: {res.stderr or res.stdout}")

    def _handle_reject_worktree(self, payload: dict) -> None:
        run_id = payload.get("run_id")
        if not run_id:
            self._send_error_json("Missing run_id")
            return
        for s_root in [
            self.vault_root.parent / ".orchestration-state",
            self.vault_root / ".orchestration-state",
            REPO_ROOT.parent / ".orchestration-state",
            REPO_ROOT / ".orchestration-state",
        ]:
            run_dir = s_root / run_id
            if run_dir.is_dir():
                shutil.rmtree(run_dir, ignore_errors=True)
        self._send_json({"success": True, "message": f"Run {run_id} silindi."})

    def _handle_run_briefing(self) -> None:
        script = self.vault_root / ".beyin" / "morning_briefing.py"
        if not script.is_file():
            script = REPO_ROOT / "template" / ".beyin" / "morning_briefing.py"
        cmd = [sys.executable, str(script), "--apply"]
        res = subprocess.run(cmd, cwd=self.vault_root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            self._send_json({"success": True, "message": "Sabah brifingi başarıyla üretildi."})
        else:
            self._send_error_json(f"Brifing hatası: {res.stderr or res.stdout}")

    def _handle_run_compile(self) -> None:
        script = self.vault_root / ".beyin" / "engine" / "compile.py"
        if not script.is_file():
            script = REPO_ROOT / "template" / ".beyin" / "engine" / "compile.py"
        cmd = [sys.executable, str(script)]
        res = subprocess.run(cmd, cwd=self.vault_root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            self._send_json({"success": True, "message": "Bilgi derleme başarıyla tamamlandı."})
        else:
            self._send_error_json(f"Derleme hatası: {res.stderr or res.stdout}")

    def _handle_run_doctor(self) -> None:
        state_dir = self.vault_root / ".beyin" / "engine" / ".state"
        health = _read_json_safe(state_dir / "health.json", {})
        briefing_health = _read_json_safe(state_dir / "briefing-health.json", {})
        compile_state = _read_json_safe(state_dir / "compile-state.json", {})
        has_error = bool(health.get("error"))
        status = "healthy" if not has_error else "degraded"
        report = {
            "status": status,
            "engine_health": health,
            "briefing_health": briefing_health,
            "compile_state": compile_state,
        }
        status_msg = "Mükemmel ✓ (Tüm sistemler aktif)" if status == "healthy" else "İnceleme Gerekli ⚠️"
        self._send_json({
            "success": True,
            "report": report,
            "message": f"Kasa sağlığı: {status_msg}",
        })

    def _handle_run_reindex(self) -> None:
        try:
            import arama
            engine = arama.SearchEngine(self.vault_root)
            count = engine.index_vault()
            self._send_json({
                "success": True,
                "indexed": count,
                "message": f"FTS5 tam metin indeksi yenilendi ({count} not tarandı)."
            })
        except Exception as e:
            self._send_error_json(f"İndeksleme hatası: {e}")

    def _handle_quick_capture(self, payload: dict) -> None:
        title = payload.get("title", "").strip() or "Hızlı Not"
        content = payload.get("content", "").strip()
        category = payload.get("category", "Dump").strip()
        tags = payload.get("tags", ["quick-capture"])

        if not content:
            self._send_error_json("Not içeriği boş olamaz")
            return

        import datetime as dt, re
        safe_slug = re.sub(r"[^\w\s-]", "", title.lower())
        safe_slug = re.sub(r"[-\s]+", "-", safe_slug).strip("-")[:40] or "note"
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_slug}.md"

        dump_dir = self.vault_root / "📥 000-Inbox" / "Dump"
        dump_dir.mkdir(parents=True, exist_ok=True)
        target = dump_dir / filename

        tag_list_str = "\n".join(f"  - {t}" for t in tags)
        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = (
            f"---\n"
            f'title: "{title}"\n'
            f'created: "{now_str}"\n'
            f'type: capture\n'
            f'category: "{category}"\n'
            f'status: inbox\n'
            f'source: web_gateway\n'
            f'tags:\n'
            f'{tag_list_str}\n'
            f"---\n\n"
            f"# {title}\n\n"
            f"{content}\n"
        )
        target.write_text(body, encoding="utf-8")

        # Re-index incrementally
        try:
            import arama
            arama.SearchEngine(self.vault_root).index_vault()
        except Exception:
            pass

        self._send_json({"success": True, "message": f"'{filename}' kaydedildi ve FTS5 indeksine eklendi."})

    def _serve_static(self, path: str) -> None:
        clean_path = path.lstrip("/")
        if not clean_path or clean_path == "index.html":
            file_path = STATIC_DIR / "index.html"
        else:
            file_path = (STATIC_DIR / clean_path).resolve()

        try:
            file_path.relative_to(STATIC_DIR)
        except ValueError:
            self._send_error_json("Access denied", 403)
            return

        if not file_path.is_file():
            file_path = STATIC_DIR / "index.html"

        if not file_path.is_file():
            self._send_error_json("Static file not found", 404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self._send_error_json("Failed to read file", 500)


def start_server(vault_root: Path, port: int = 8520, open_browser: bool = False) -> None:
    DashboardHandler.vault_root = vault_root.resolve()
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print(f"\n[+] Respected Brain Gateway & Dashboard calisiyor:")
    print(f"    URL: {url}")
    print(f"    Kasa: {DashboardHandler.vault_root}")
    print("    Durdurmak icin Ctrl+C tuslayin.\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatılıyor...")
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respected Brain Gateway & Web Dashboard")
    parser.add_argument("--vault", type=Path, default=VAULT_ROOT, help="Hedef vault kök dizini")
    parser.add_argument("--port", type=int, default=8520, help="Web sunucu portu (varsayılan: 8520)")
    parser.add_argument("--open", action="store_true", help="Tarayıcıda otomatik aç")
    args = parser.parse_args(argv)

    start_server(args.vault, args.port, args.open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
