"""Application command dispatcher."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, date
import json
from pathlib import Path
import sys

from . import __version__
from .bootstrap import application_roots, bootstrap
from .core.config import ConfigStore
from .core.errors import FoundationError, SelectionError
from .vault.registry import VaultRegistry


def _selector(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--vault", type=Path)
    group.add_argument("--vault-id")


def _parser():
    parser = argparse.ArgumentParser(prog="respectedbrain", description="Respected Brain")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    vault = commands.add_parser("vault", help="Kasa kaydı ve açık keşif")
    actions = vault.add_subparsers(dest="action", required=True)
    register = actions.add_parser("register")
    register.add_argument("path", type=Path)
    register.add_argument("--new-identity", action="store_true")
    actions.add_parser("list")
    discover = actions.add_parser("discover")
    discover.add_argument("path", type=Path)
    configure = commands.add_parser("configure", help="Kullanıcı tercihlerini göster veya değiştir")
    configure.add_argument("--summary-provider", choices=("auto", "codex", "claude", "antigravity", "gemini", "cursor"))
    for name in ("briefing", "maps"):
        _selector(commands.add_parser(name))
    compile_parser = commands.add_parser("compile")
    _selector(compile_parser)
    compile_parser.add_argument("--trigger-claim", type=Path)
    compile_parser.add_argument("--before-date", type=date.fromisoformat)
    compile_parser.add_argument("--max-calls", type=int)
    compile_parser.add_argument("--dry-run", action="store_true")
    flush = commands.add_parser("flush")
    _selector(flush)
    flush.add_argument("--hook-input", type=Path)
    flush.add_argument("--transcript", type=Path)
    flush.add_argument("--session-id")
    flush.add_argument("--reason", default="sessionend")
    flush.add_argument("--maybe-compile", action="store_true")
    dashboard = commands.add_parser("dashboard")
    _selector(dashboard)
    dashboard.add_argument("--port", type=int, default=8520)
    dashboard.add_argument("--open", action="store_true")
    search = commands.add_parser("search")
    _selector(search)
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--reindex", action="store_true")
    search.add_argument("--category")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--json", action="store_true")
    orchestrate = commands.add_parser("orchestrate")
    _selector(orchestrate)
    orchestrate.add_argument("--project-root", type=Path, required=True)
    orchestrate.add_argument("argv", nargs=argparse.REMAINDER)
    maintenance = commands.add_parser("maintenance")
    _selector(maintenance)
    maintenance.add_argument("name")
    maintenance.add_argument("argv", nargs=argparse.REMAINDER)
    return parser


def _dispatch(args) -> int:
    if args.command in ("vault", "configure"):
        roots = application_roots()
        store = ConfigStore(roots.data_root)
        if args.command == "configure":
            if args.summary_provider is not None:
                config = store.update(lambda value: value["preferences"].update(summary_provider=args.summary_provider))
            else:
                config = store.read()
            print(json.dumps(config, ensure_ascii=False, indent=2))
            return 0
        registry = VaultRegistry(store)
        if args.action == "register":
            print(registry.register(args.path, new_identity=args.new_identity))
        elif args.action == "list":
            print(json.dumps(registry.list(), ensure_ascii=False, indent=2))
        else:
            found = registry.discover(args.path)
            if found is None:
                raise SelectionError("Kayıtlı kasa bulunamadı; vault register ile kaydedin.")
            print(found)
        return 0
    ctx = bootstrap(vault=args.vault, vault_id=args.vault_id)
    now = datetime.now().astimezone()
    if args.command in ("compile", "briefing", "flush"):
        from .providers.runner import ModelRunner
        model = ModelRunner(ctx)
        if args.command == "compile":
            from .memory.compile import compile_memory, compile_pending, DEFAULT_MAX_CALLS
            if args.trigger_claim or args.before_date or args.max_calls is not None or args.dry_run:
                return compile_pending(ctx, model=model, now=now, trigger_claim=args.trigger_claim,
                                       before_date=args.before_date, max_calls=args.max_calls if args.max_calls is not None else DEFAULT_MAX_CALLS,
                                       dry_run=args.dry_run)
            return compile_memory(ctx, model=model, now=now)
        if args.command == "flush":
            from .memory.flush import flush_transcript, load_hook_input, _managed_hook_input, compile_catch_up, catch_up_unflushed_sessions
            if args.maybe_compile:
                catch_up_unflushed_sessions(ctx, model=model, now=now, home=Path.home())
                return compile_catch_up(ctx, model=model, now=now)
            value = load_hook_input(args.hook_input) if args.hook_input is not None else {}
            session = args.session_id or value.get("session_id")
            transcript = args.transcript or (Path(value["transcript_path"]) if value.get("transcript_path") else None)
            if not session or transcript is None:
                raise SelectionError("flush requires a session and transcript")
            status = flush_transcript(ctx, session_id=session, transcript=transcript, model=model, now=now, reason=args.reason)
            if args.hook_input is not None and _managed_hook_input(args.hook_input, ctx.paths.state_dir):
                args.hook_input.unlink(missing_ok=True)
            return status
        from .briefing.service import run_if_due
        return run_if_due(ctx, model=model, now=now)
    if args.command == "maps":
        from .vault.maps import rebuild_maps
        rebuild_maps(ctx)
        return 0
    if args.command == "dashboard":
        from .gateway.server import start_server
        start_server(ctx, port=args.port, open_browser=args.open)
        return 0
    if args.command == "search":
        from .search.engine import SearchEngine
        engine = SearchEngine(ctx)
        stats = engine.index_vault(force=args.reindex)
        if args.query:
            results = engine.search(args.query, limit=args.limit, category=args.category)
            print(json.dumps(results, ensure_ascii=False, indent=2) if args.json else "\n".join(f"{r['title']} ({r['path']})\n{r['snippet']}" for r in results))
        else:
            print(json.dumps(stats, ensure_ascii=False))
        return 0
    if args.command == "orchestrate":
        from .orchestration.runner import run
        return run(ctx, project_root=args.project_root, argv=args.argv)
    from .maintenance import run_tool
    return run_tool(ctx, name=args.name, argv=args.argv)


def main(argv: Sequence[str] | None = None) -> int:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            configure = getattr(stream, "reconfigure", None)
            if callable(configure):
                configure(encoding="utf-8", errors="replace")
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if args.command is None:
            parser.print_help()
            return 0
        return _dispatch(args)
    except SystemExit as error:
        return int(error.code)
    except (SelectionError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except (FoundationError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
