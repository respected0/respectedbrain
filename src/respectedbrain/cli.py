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
    setup_parser = commands.add_parser("setup")
    setup_parser.add_argument("--vault", type=Path)
    setup_parser.add_argument("--package", type=Path)
    setup_parser.add_argument("--gui", action="store_true")
    setup_parser.add_argument("--user-name")
    setup_parser.add_argument("--user-bio")
    setup_parser.add_argument("--companion")
    setup_parser.add_argument("--os-name")
    setup_parser.add_argument("--summary-provider", choices=("auto", "codex", "claude", "antigravity", "gemini", "cursor"))
    setup_parser.add_argument("--platform", choices=("windows-native", "posix", "windows-wsl"))
    for flag in ("global", "mcp", "schedule", "shortcut"):
        setup_parser.add_argument("--" + flag, dest="desired_" + flag, action=argparse.BooleanOptionalAction, default=None)
    for name in ("update", "repair", "uninstall"):
        operation = commands.add_parser(name)
        _selector(operation)
        if name == "update":
            operation.add_argument("--package", type=Path, required=True)
        if name == "uninstall":
            operation.add_argument("--purge-data", action="store_true")
    migrate = commands.add_parser("migrate")
    migrate.add_argument("--legacy-root", type=Path, required=True)
    migrate.add_argument("--vault", type=Path, required=True)
    migrate.add_argument("--package", type=Path)
    migrate.add_argument("--apply", action="store_true")
    migrate.add_argument("--platform", choices=("windows-native", "posix", "windows-wsl"))
    commands.add_parser("recover")
    hook = commands.add_parser("hook")
    _selector(hook)
    hook.add_argument("--provider", required=True, choices=("claude", "codex", "cursor", "antigravity", "gemini"))
    hook.add_argument("--event", required=True, choices=("start", "prompt", "precompact", "postcompact", "turn", "end", "notify"))
    hook.add_argument("--global-hook", action="store_true")
    hook.add_argument("--chain-file", type=Path)
    hook.add_argument("payload", nargs=argparse.REMAINDER)
    _selector(commands.add_parser("mcp"))
    resume = commands.add_parser("_resume-operation", help=argparse.SUPPRESS)
    resume.add_argument("--request", type=Path, required=True)
    resume.add_argument("--request-hash", required=True)
    for name in ("_inno-prepare", "_inno-deploy", "_inno-uninstall", "_inno-seal", "_inno-launch"):
        shell = commands.add_parser(name, help=argparse.SUPPRESS)
        shell.add_argument("--app-root", type=Path, required=True)
        shell.add_argument("--data-root", type=Path, required=True)
        shell.add_argument("--vault", type=Path, required=True)
        if name in ("_inno-prepare", "_inno-deploy"):
            shell.add_argument("--request", type=Path, required=True)
        if name == "_inno-prepare":
            shell.add_argument("--registry-key")
        if name == "_inno-deploy":
            shell.add_argument("--package", type=Path, required=True)
        if name == "_inno-uninstall":
            shell.add_argument("--proof", type=Path, required=True)
            shell.add_argument("--proof-hash", required=True)
    copy = commands.add_parser("_inno-copy-helper", help=argparse.SUPPRESS)
    copy.add_argument("--app-root", type=Path, required=True)
    copy.add_argument("--output", type=Path, required=True)
    return parser


def _dispatch(args) -> int:
    if args.command == "_inno-copy-helper":
        from .installation.windows import copy_helper
        copy_helper(args.app_root, args.output)
        return 0
    if args.command.startswith("_inno-"):
        from .core.paths import Roots
        from .integrations.backend import NativeBackend, INNO_UNINSTALL_KEY
        from .installation.windows import prepare_shell, deploy_shell, seal_shell
        roots = Roots(args.app_root.resolve(), args.data_root.resolve(), args.vault.resolve())
        backend = NativeBackend(roots.data_root)
        if args.command == "_inno-seal":
            return _operation_output(seal_shell(roots, backend=backend))
        if args.command == "_inno-prepare":
            prepare_shell(roots, request=args.request, registry_key=args.registry_key or INNO_UNINSTALL_KEY, backend=backend)
            return 0
        if args.command == "_inno-deploy":
            return _operation_output(deploy_shell(roots, package=args.package.resolve(), request=args.request, backend=backend))
        from .vault.registry import build_context
        from .installation.uninstall import uninstall
        ctx = build_context(roots, ConfigStore(roots.data_root), vault=None, vault_id=None, env={})
        if args.command == "_inno-launch":
            from .installation.deferred import defer_operation
            pending = defer_operation(ctx, mode="uninstall")
            return _operation_output(pending if pending is not None else uninstall(ctx, backend=backend))
        from .installation.windows import validate_uninstall_proof
        result = uninstall(ctx, backend=backend, shell_active=True, shell_proof=lambda: validate_uninstall_proof(roots, request=args.proof, expected_hash=args.proof_hash))
        from .core.config import atomic_write_json
        from dataclasses import asdict
        atomic_write_json(roots.data_root / "logs/uninstall-result.json", asdict(result))
        return _operation_output(result)
    if args.command in ("compile", "flush"):
        from .memory.lifecycle import _is_reentrant
        if _is_reentrant():
            return 0
    if args.command == "_resume-operation":
        from .installation.deferred import resume_operation
        return resume_operation(args.request, expected_hash=args.request_hash)
    if args.command in ("setup", "migrate", "recover"):
        roots = application_roots()
        from .integrations.backend import NativeBackend
        backend = NativeBackend(roots.data_root)
        if args.command == "recover":
            from .installation.transaction import recover_transactions
            from dataclasses import asdict
            results = recover_transactions(roots.data_root, backend)
            print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
            return 1 if any(result.conflicts for result in results) else 0
        if args.command == "migrate":
            from .installation.common import installed_profile
            from .installation.migration import plan_migration, plan_document
            profile = {"platform": args.platform} if args.platform else {}
            plan = plan_migration(args.legacy_root.resolve(), args.vault.resolve(), roots=roots, backend=backend, profile=installed_profile(roots, profile))
            if not args.apply:
                print(json.dumps(plan_document(plan), ensure_ascii=False, indent=2))
                return 1 if plan.conflicts else 0
            from .installation.migration import apply_migration
            result = apply_migration(plan, roots=roots, package=args.package or roots.app_root, backend=backend)
            return _operation_output(result)
        desired_overrides = {key: getattr(args, "desired_" + key) for key in ("global", "mcp", "schedule", "shortcut") if getattr(args, "desired_" + key) is not None}
        profile = {key: value for key, value in {"USER_NAME": args.user_name, "USER_BIO": args.user_bio, "COMPANION": args.companion, "OS_NAME": args.os_name, "summary_provider": args.summary_provider, "platform": args.platform}.items() if value is not None}
        vault = args.vault.resolve() if args.vault is not None else None
        package = args.package.resolve() if args.package is not None else None
        if args.gui:
            from .installation.wizard import main as wizard_main
            return wizard_main(roots=roots, backend=backend, vault=vault, package=package, profile=profile, desired=desired_overrides)
        from .installation.setup import setup
        desired = ConfigStore(roots.data_root).read()["integrations"]
        desired = {key: desired_overrides.get(key, desired.get(key, False)) for key in ("global", "mcp", "schedule", "shortcut")}
        return _operation_output(setup(roots, vault if vault is not None else roots.default_vault, profile=profile, desired=desired, backend=backend, package=package))
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
    if args.command == "hook":
        from .integrations.hooks.bridge import dispatch
        arguments = (["--global-hook"] if args.global_hook else []) + args.payload
        if args.chain_file is not None:
            arguments = ["--chain-file", str(args.chain_file), *arguments]
        sys.stdout.write(dispatch(ctx, provider=args.provider, event=args.event, argv=arguments, stdin=sys.stdin.read()))
        sys.stdout.flush()
        return 0
    if args.command == "mcp":
        from .integrations.mcp.server import serve
        return serve(ctx)
    if args.command in ("update", "repair", "uninstall"):
        from .integrations.backend import NativeBackend
        backend = NativeBackend(ctx.paths.data_root)
        if args.command in ("update", "uninstall"):
            from .installation.deferred import defer_operation
            queued = defer_operation(ctx, mode=args.command, package=args.package.resolve() if args.command == "update" else None, purge_data=getattr(args, "purge_data", False))
            if queued is not None:
                return _operation_output(queued)
        if args.command == "update":
            from .installation.update import update
            return _operation_output(update(ctx, package=args.package.resolve(), backend=backend))
        if args.command == "repair":
            from .installation.repair import repair
            return _operation_output(repair(ctx, backend=backend))
        from .installation.uninstall import uninstall
        return _operation_output(uninstall(ctx, backend=backend, purge_data=args.purge_data))
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


def _operation_output(result) -> int:
    from dataclasses import asdict
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.success or result.pending else 1


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
