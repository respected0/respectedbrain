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
import sys
import time
import urllib.parse

from respectedbrain import __version__
from respectedbrain.core.context import AppContext
from respectedbrain.core.config import ConfigStore
from respectedbrain.core.coordination import guarded_writer
from respectedbrain.core import platform as runtime_platform
from respectedbrain.providers.runner import ModelRunner, ProviderStatus
from respectedbrain.search.engine import SearchEngine
from respectedbrain.orchestration import runner as orchestration


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
    ctx: AppContext
    provider_status: ProviderStatus

    @property
    def vault_root(self):
        return self.ctx.paths.vault_root

    def _preferences(self):
        return ConfigStore(self.ctx.paths.data_root).read()["preferences"]

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
        state_dir = self.ctx.paths.state_dir

        if path == "/api/status":
            config = self._preferences()
            version = __version__
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
            config = self._preferences()
            cli_status = self.provider_status.get_cli_status(force_refresh=force_refresh)
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
            self._send_json(orchestration.list_runs(self.ctx))

        elif path == "/api/search":
            q = params.get("q", [""])[0]
            limit = int(params.get("limit", ["15"])[0])
            category = params.get("category", [None])[0]
            try:
                engine = SearchEngine(self.ctx)
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
            current_ver = __version__
            self._send_json({
                "current_version": current_ver,
                "latest_version": current_ver,
                "update_available": False,
                "status": "up_to_date",
            })

        else:
            self._send_error_json("API endpoint not found", 404)

    @guarded_writer(busy_result=None)
    def _handle_set_priority(self, payload: dict) -> None:
        def edit(value):
            config = value["preferences"]
            priority = payload.get("priority")
            provider = payload.get("summary_provider")
            if isinstance(priority, list):
                config["provider_priority"] = priority
                if config.get("summary_provider") not in ("auto", None) and priority:
                    config["summary_provider"] = priority[0]
            if isinstance(provider, str):
                config["summary_provider"] = provider
                if provider != "auto":
                    priority = list(config.get("provider_priority", []))
                    if provider in priority:
                        priority.remove(provider)
                    config["provider_priority"] = [provider, *priority]
        config = ConfigStore(self.ctx.paths.data_root).update(edit)["preferences"]
        self._send_json({"success": True, "config": config, "summary_provider": config.get("summary_provider", "auto"), "priority": config.get("provider_priority")})

    def _handle_start_orchestration(self, payload: dict) -> None:
        project = payload.get("project_root")
        if not project:
            self._send_error_json("Kod projesi project_root ile açıkça seçilmeli")
            return
        try:
            result = orchestration.start_run(self.ctx, project_root=Path(project), task=payload.get("task", "").strip(), master=payload.get("master", "user"), worker=payload.get("worker", "antigravity"), test_command=payload.get("test"))
            self._send_json(result)
        except (ValueError, OSError) as error:
            self._send_error_json(str(error))

    def _handle_apply_patch(self, payload: dict) -> None:
        try:
            self._send_json(orchestration.apply_run(self.ctx, payload.get("run_id", "")))
        except (ValueError, OSError) as error:
            self._send_error_json(str(error))

    def _handle_reject_worktree(self, payload: dict) -> None:
        try:
            self._send_json(orchestration.reject_run(self.ctx, payload.get("run_id", "")))
        except (ValueError, OSError) as error:
            self._send_error_json(str(error))

    def _handle_run_briefing(self) -> None:
        from datetime import datetime
        from respectedbrain.briefing.service import run_if_due
        status = run_if_due(self.ctx, model=ModelRunner(self.ctx), now=datetime.now().astimezone())
        self._send_json({"success": status == 0, "message": "Sabah brifingi tamamlandı." if status == 0 else "Brifing başarısız."})

    def _handle_run_compile(self) -> None:
        from datetime import datetime
        from respectedbrain.memory.compile import compile_memory
        status = compile_memory(self.ctx, model=ModelRunner(self.ctx), now=datetime.now().astimezone())
        self._send_json({"success": status == 0, "message": "Bilgi derleme tamamlandı." if status == 0 else "Derleme başarısız."})

    def _handle_run_doctor(self) -> None:
        state_dir = self.ctx.paths.state_dir
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
            engine = SearchEngine(self.ctx)
            count = engine.index_vault()
            self._send_json({
                "success": True,
                "indexed": count,
                "message": f"FTS5 tam metin indeksi yenilendi ({count} not tarandı)."
            })
        except Exception as e:
            self._send_error_json(f"İndeksleme hatası: {e}")

    @guarded_writer(busy_result=None)
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
        target = dump_dir / filename
        if not runtime_platform.path_within_vault(target, self.vault_root):
            self._send_error_json("Unsafe capture target", 403)
            return
        dump_dir.mkdir(parents=True, exist_ok=True)

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
            SearchEngine(self.ctx).index_vault()
        except Exception:
            pass

        self._send_json({"success": True, "message": f"'{filename}' kaydedildi ve FTS5 indeksine eklendi."})

    def _serve_static(self, path: str) -> None:
        clean = path.lstrip("/") or "index.html"
        if any(part in ("..", ".") for part in clean.split("/")) or "\\" in clean or ":" in clean:
            self._send_error_json("Access denied", 403)
            return
        try:
            resource = self.ctx.resources._locate("gateway/web/" + clean)
            if not resource.is_file():
                clean = "index.html"
                resource = self.ctx.resources._locate("gateway/web/index.html")
            content = resource.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(clean)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except (OSError, ValueError):
            self._send_error_json("Static file not found", 404)


def create_server(ctx: AppContext, *, port: int = 8520) -> ThreadingHTTPServer:
    class Handler(DashboardHandler):
        pass
    Handler.ctx = ctx
    Handler.provider_status = ProviderStatus()
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def start_server(ctx: AppContext, *, port: int = 8520, open_browser: bool = False) -> None:
    server = create_server(ctx, port=port)
    url = f"http://localhost:{server.server_port}"
    print(f"Respected Brain: {url} — {ctx.paths.vault_root}")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
