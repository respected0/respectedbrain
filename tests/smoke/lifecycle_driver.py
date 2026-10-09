#!/usr/bin/env python3
"""Run one package lifecycle operation with strict provenance by default."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from unittest import mock

from respectedbrain.core.config import ConfigStore
from respectedbrain.core.paths import Roots
from respectedbrain.integrations.backend import NativeBackend
from respectedbrain.installation.deferred import defer_operation, resume_operation
from respectedbrain.installation.ownership import digest
from respectedbrain.installation.repair import repair
from respectedbrain.installation.setup import setup
from respectedbrain.installation.transaction import OperationResult
from respectedbrain.installation.uninstall import uninstall
from respectedbrain.installation.update import update
from respectedbrain.vault.registry import build_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("setup", "update", "repair", "deferred-update", "uninstall"))
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--vault-id")
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--summary-provider", default="claude")
    parser.add_argument("--allow-unsigned-fixture", action="store_true")
    args = parser.parse_args()
    if args.action != "setup" and not args.vault_id:
        parser.error("--vault-id is required outside setup")

    roots = Roots(args.app_root.resolve(), args.data_root.resolve(), args.vault.resolve())
    store = ConfigStore(roots.data_root)
    backend = NativeBackend(roots.data_root, user_home=args.home.resolve())
    provenance = False if args.allow_unsigned_fixture else None
    if args.action == "setup":
        result = setup(
            roots,
            roots.default_vault,
            profile={
                "OS_NAME": "RespectedOS",
                "USER_NAME": "Smoke User",
                "USER_BIO": "",
                "COMPANION": "Smoke Companion",
                "summary_provider": args.summary_provider,
                "platform": "windows-native" if os.name == "nt" else "posix",
                "user_home": str(args.home.resolve()),
            },
            desired={"global": False, "mcp": False, "schedule": False, "shortcut": False},
            backend=backend,
            package=args.package.resolve() if args.package else None,
            require_provenance=provenance,
        )
    else:
        ctx = build_context(
            roots,
            store,
            vault=None,
            vault_id=args.vault_id,
            env={},
        )
        package = args.package.resolve() if args.package else None
        if args.action == "update":
            result = update(ctx, package=package, backend=backend, require_provenance=provenance)
        elif args.action == "repair":
            result = repair(ctx, backend=backend, require_provenance=provenance)
        elif args.action == "uninstall":
            result = uninstall(ctx, backend=backend)
        else:
            if not args.allow_unsigned_fixture:
                raise RuntimeError("Real deferred update must run through the frozen launcher")
            launcher = roots.app_root / "respectedbrain.exe"
            captured = []

            def capture(*command, **kwargs):
                captured.append(command[0])
                return mock.Mock()

            with (
                mock.patch("respectedbrain.installation.deferred.sys.frozen", True, create=True),
                mock.patch("respectedbrain.installation.deferred.sys.executable", str(launcher)),
                mock.patch("respectedbrain.installation.deferred.subprocess.Popen", side_effect=capture),
                mock.patch("respectedbrain.installation.deferred._wait_parent", return_value=None),
            ):
                result = defer_operation(ctx, mode="update", package=package, require_provenance=False)
            if result is None or not captured:
                raise RuntimeError("Fixture deferred update was not queued")
            request = Path(captured[-1][captured[-1].index("--request") + 1])
            with mock.patch("respectedbrain.installation.deferred._wait_parent", return_value=None):
                resume_operation(
                    request,
                    expected_hash=digest(request),
                    require_provenance=False,
                )
            result = OperationResult(True, request.stem, (), pending=False)
    if hasattr(result, "__dataclass_fields__"):
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if getattr(result, "success", False) or getattr(result, "pending", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
