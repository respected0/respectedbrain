#!/usr/bin/env python3
"""Opt-in private Git snapshot publisher for Respected Brain vaults."""

from __future__ import annotations

from respectedbrain.core.context import AppContext
from respectedbrain.maintenance import selected_vault, mutable_target

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any






def _atomic_write(path: Path, content: str) -> None:
    """Write text atomically via temporary file and replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise




class SecretFinding(str):
    """Guarded finding identifier holding only path and safe category, never secret values."""

    def __new__(cls, path: str, category: str = "forbidden-file"):
        obj = super().__new__(cls, path)
        obj.path = path
        obj.category = category
        return obj

    def get(self, key: str, default: Any = None) -> Any:
        if key == "path":
            return self.path
        if key == "category":
            return self.category
        return default

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "category": self.category}


FORBIDDEN_NAME_PATTERNS = (
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"^.*id_rsa.*$", re.IGNORECASE),
    re.compile(r"^.*\.(pem|key|pfx|pkcs12)$", re.IGNORECASE),
    re.compile(r"^.*settings\.local\.json$", re.IGNORECASE),
    re.compile(r"^.*credentials.*$", re.IGNORECASE),
)

CONTENT_SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")),
    ("provider-token", re.compile(r"(?:\b|(?<=['\"`\s:=]))sk-[a-zA-Z0-9_-]{20,}\b")),
    ("provider-token", re.compile(r"(?:\b|(?<=['\"`\s:=]))sk-ant-[a-zA-Z0-9_-]{20,}\b")),
    ("provider-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9_]{16,}\b")),
    ("provider-token", re.compile(r"\bhf_[a-zA-Z0-9]{20,}\b")),
    ("provider-token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z-]{10,}\b")),
    ("cloud-credential", re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")),
    ("generic-secret", re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?token|auth[_-]?token)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{16,}['\"]")),
)


def scan_file_content_for_secrets(
    file_path: Path,
    vault_root: Path,
    chunk_size: int = 64 * 1024,
    max_file_size: int = 50 * 1024 * 1024,
) -> SecretFinding | None:
    """Scan file content using sliding window buffering without persisting or leaking secrets."""
    try:
        rel = Path(file_path).relative_to(vault_root).as_posix()
    except ValueError:
        rel = str(file_path)

    # Symlink / reparse escape check
    try:
        resolved = file_path.resolve()
        resolved.relative_to(vault_root.resolve())
    except (ValueError, OSError):
        return SecretFinding(rel, "link-escape")

    if file_path.is_symlink():
        try:
            target = Path(os.readlink(file_path))
            target_res = (file_path.parent / target).resolve()
            target_res.relative_to(vault_root.resolve())
        except (ValueError, OSError):
            return SecretFinding(rel, "link-escape")

    # File size limit check
    try:
        size = file_path.stat().st_size
        if size > max_file_size:
            return SecretFinding(rel, "file-too-large")
    except OSError:
        return SecretFinding(rel, "read-error")

    # Sliding window chunk reading (with overlap to catch patterns split across boundary)
    overlap = 512
    prev_overlap = ""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                window = prev_overlap + chunk
                for category, pattern in CONTENT_SECRET_PATTERNS:
                    if pattern.search(window):
                        return SecretFinding(rel, category)
                prev_overlap = chunk[-overlap:] if len(chunk) >= overlap else chunk
    except Exception:
        return SecretFinding(rel, "read-error")

    return None


def check_secret_guard(vault_root: Path) -> tuple[bool, list[SecretFinding]]:
    """Scan vault candidates (both git tracked/untracked and files) for secrets and forbidden names."""
    candidate_paths: set[str] = set()

    # 1. Enumerate git files (including ignored but already tracked files)
    if (vault_root / ".git").is_dir():
        try:
            tracked = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=vault_root,
                capture_output=True,
                check=False,
            )
            if tracked.returncode == 0:
                for entry in tracked.stdout.split(b"\0"):
                    if entry:
                        candidate_paths.add(entry.decode("utf-8", errors="replace"))

            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "-z"],
                cwd=vault_root,
                capture_output=True,
                check=False,
            )
            if untracked.returncode == 0:
                for entry in untracked.stdout.split(b"\0"):
                    if entry:
                        candidate_paths.add(entry.decode("utf-8", errors="replace"))
        except (OSError, subprocess.SubprocessError):
            pass

    # 2. Supplement with os.walk for non-git directories or newly added files
    for current, dirs, files in os.walk(vault_root, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "venv", "__pycache__"}]
        for file_name in files:
            rel = Path(current, file_name).relative_to(vault_root).as_posix()
            candidate_paths.add(rel)

    findings: list[SecretFinding] = []
    for rel in sorted(candidate_paths):
        file_path = vault_root / rel
        file_name = file_path.name

        # Filename pattern check
        matched = False
        for pattern in FORBIDDEN_NAME_PATTERNS:
            if pattern.match(file_name):
                findings.append(SecretFinding(rel, "forbidden-filename"))
                matched = True
                break
        if matched:
            continue

        if file_path.is_file() or file_path.is_symlink():
            content_finding = scan_file_content_for_secrets(file_path, vault_root)
            if content_finding is not None:
                findings.append(content_finding)

    return len(findings) == 0, findings



def _resolve_git_dir(vault_root: Path) -> Path | None:
    git_path = vault_root / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                target = content[len("gitdir:"):].strip()
                target_path = Path(target)
                resolved = target_path if target_path.is_absolute() else (vault_root / target_path).resolve()
                if resolved.is_dir():
                    return resolved
        except OSError:
            return None
    return None


def scan_git_index_for_secrets(
    vault_root: Path,
    max_file_size: int = 50 * 1024 * 1024,
    index_file: Path | None = None,
) -> tuple[bool, list[SecretFinding]]:
    """Scan staged Git index blob contents directly for secrets and forbidden filenames.

    Guarantees secrets staged in the Git index (even if cleaned in the working tree)
    are detected and prevented from committing. Fail-closed on errors.
    """
    git_dir = _resolve_git_dir(vault_root)
    if git_dir is None:
        if (vault_root / ".git").exists():
            return False, [SecretFinding(".", "git-dir-missing-or-invalid")]
        git_dir = vault_root / ".git"

    if index_file is None and not (git_dir / "index").is_file():
        return True, []

    findings: list[SecretFinding] = []
    cmd_env = os.environ.copy()
    if index_file is not None:
        cmd_env["GIT_INDEX_FILE"] = str(index_file)
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=vault_root,
            capture_output=True,
            check=False,
            env=cmd_env,
        )
        if proc.returncode != 0:
            return False, [SecretFinding(".", "git-index-error")]

        raw_stdout = proc.stdout.encode("utf-8") if isinstance(proc.stdout, str) else (proc.stdout or b"")
        if not raw_stdout:
            return True, []

        entries = raw_stdout.split(b"\0")
        for raw in entries:
            if not raw:
                continue
            try:
                meta, path_str = raw.split(b"\t", 1)
                rel_path = path_str.decode("utf-8", errors="replace")
                meta_parts = meta.split()
                if len(meta_parts) < 3:
                    continue
                blob_sha = meta_parts[1].decode("ascii", errors="replace")
            except Exception:
                return False, [SecretFinding(".", "git-index-parse-error")]

            # 1. Filename pattern check
            file_name = Path(rel_path).name
            matched = False
            for pattern in FORBIDDEN_NAME_PATTERNS:
                if pattern.match(file_name):
                    findings.append(SecretFinding(rel_path, "forbidden-filename"))
                    matched = True
                    break
            if matched:
                continue

            # 2. Check blob size and content via git cat-file
            try:
                size_proc = subprocess.run(
                    ["git", "cat-file", "-s", blob_sha],
                    cwd=vault_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if size_proc.returncode != 0:
                    findings.append(SecretFinding(rel_path, "read-error"))
                    continue
                blob_size = int(size_proc.stdout.strip())
                if blob_size > max_file_size:
                    findings.append(SecretFinding(rel_path, "file-too-large"))
                    continue

                cat_proc = subprocess.run(
                    ["git", "cat-file", "-p", blob_sha],
                    cwd=vault_root,
                    capture_output=True,
                    check=False,
                )
                if cat_proc.returncode != 0:
                    findings.append(SecretFinding(rel_path, "read-error"))
                    continue

                blob_bytes = cat_proc.stdout
                overlap = 512
                chunk_size = 64 * 1024
                offset = 0
                prev_overlap = ""
                blob_str = blob_bytes.decode("utf-8", errors="replace")
                while offset < len(blob_str):
                    chunk = blob_str[offset:offset + chunk_size]
                    offset += chunk_size
                    window = prev_overlap + chunk
                    pattern_found = False
                    for category, pattern in CONTENT_SECRET_PATTERNS:
                        if pattern.search(window):
                            findings.append(SecretFinding(rel_path, category))
                            pattern_found = True
                            break
                    if pattern_found:
                        break
                    prev_overlap = chunk[-overlap:] if len(chunk) >= overlap else chunk
            except Exception:
                findings.append(SecretFinding(rel_path, "read-error"))

    except Exception:
        return False, [SecretFinding(".", "git-index-scan-error")]

    return len(findings) == 0, findings



def scan_git_tree_for_secrets(
    vault_root: Path,
    tree_sha: str,
    max_file_size: int = 50 * 1024 * 1024,
) -> tuple[bool, list[SecretFinding]]:
    git_dir = _resolve_git_dir(vault_root)
    if git_dir is None:
        return False, [SecretFinding('.', 'git-dir-missing-or-invalid')]
    tree_index = git_dir / f'index.tree_{os.getpid()}_{time.time_ns()}'
    env = {**os.environ, 'GIT_INDEX_FILE': str(tree_index)}
    try:
        check = subprocess.run(
            ['git', 'cat-file', '-t', tree_sha],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode != 0 or check.stdout.strip() != 'tree':
            return False, [SecretFinding('.', 'immutable-tree-invalid')]
        loaded = subprocess.run(
            ['git', 'read-tree', tree_sha],
            cwd=vault_root,
            env=env,
            capture_output=True,
            check=False,
        )
        if loaded.returncode != 0:
            return False, [SecretFinding('.', 'immutable-tree-load-error')]
        return scan_git_index_for_secrets(vault_root, max_file_size=max_file_size, index_file=tree_index)
    finally:
        tree_index.unlink(missing_ok=True)


def _remote_ref(vault_root: Path, remote: str, branch: str) -> tuple[str | None, str]:
    '''Return the live remote ref, or None and a safe error reason.'''
    try:
        remote_proc = subprocess.run(
            ['git', 'ls-remote', remote, f'refs/heads/{branch}'],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if remote_proc.returncode != 0:
        detail = remote_proc.stderr.strip() or 'git ls-remote failed'
        return None, detail
    fields = remote_proc.stdout.split()
    return (fields[0] if fields else ''), ''


def _branch_divergence_status(
    vault_root: Path,
    remote: str,
    branch: str,
    *,
    receipt_commit: str | None = None,
) -> str:
    """Determine if local branch has diverged from remote without pulling."""
    try:
        top_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if top_proc.returncode != 0:
            return "unknown"
        try:
            if not os.path.samefile(top_proc.stdout.strip(), vault_root):
                return "unknown"
        except (OSError, ValueError):
            return "unknown"
        # Fetch remote updates cleanly
        fetch = subprocess.run(
            ["git", "fetch", remote, branch],
            cwd=vault_root,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if fetch.returncode != 0:
            return "error"
        head_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        remote_proc = subprocess.run(
            ["git", "rev-parse", f"{remote}/{branch}"],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if head_proc.returncode != 0 or remote_proc.returncode != 0:
            return "unknown"
        head_hash = head_proc.stdout.strip()
        remote_hash = remote_proc.stdout.strip()
        if head_hash == remote_hash:
            return "clean"

        base_proc = subprocess.run(
            ["git", "merge-base", head_hash, remote_hash],
            cwd=vault_root,
            capture_output=True,
            text=True,
            check=False,
        )
        base_hash = base_proc.stdout.strip()
        if base_hash == head_hash:
            return "behind"
        if receipt_commit and remote_hash == receipt_commit:
            return 'snapshot_chain'
        if base_hash == remote_hash:
            return "ahead"
        return "diverged"
    except (OSError, subprocess.SubprocessError):
        return "error"


def _publish_immutable_snapshot(
    vault_root: Path,
    remote: str,
    branch: str,
    receipt_file: Path,
    now_epoch: float,
    stamp: str,
    remote_parent: str,
) -> dict[str, Any]:
    git_dir = _resolve_git_dir(vault_root)
    if git_dir is None:
        return {'status': 'halted:git_dir_invalid', 'detail': 'Git directory missing or invalid; fail-closed.'}
    live_index = git_dir / 'index'
    user_index_before = live_index.read_bytes() if live_index.is_file() else None
    head_result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=vault_root, capture_output=True, text=True, check=False)
    parent_sha = head_result.stdout.strip() if head_result.returncode == 0 else ''
    isolated_index = git_dir / f'index.snapshot_{os.getpid()}_{time.time_ns()}'
    iso_env = {**os.environ, 'GIT_INDEX_FILE': str(isolated_index)}
    try:
        if user_index_before is not None:
            isolated_index.write_bytes(user_index_before)
        elif parent_sha:
            subprocess.run(['git', 'read-tree', parent_sha], cwd=vault_root, env=iso_env, check=True, capture_output=True)
        else:
            subprocess.run(['git', 'read-tree', '--empty'], cwd=vault_root, env=iso_env, check=True, capture_output=True)
        listed = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=vault_root, env=iso_env, check=False, capture_output=True)
        if listed.returncode != 0:
            return {'status': 'halted:user_index_invalid', 'detail': 'Copied user index could not be validated; fail-closed.'}
        captured_index = isolated_index.read_bytes()
        captured_safe, captured_forbidden = scan_git_index_for_secrets(vault_root, index_file=isolated_index)
        if isolated_index.read_bytes() != captured_index:
            return {'status': 'halted:user_state_changed', 'detail': 'Captured user index changed during immutable scan; nothing published.'}
        if not captured_safe:
            return {'status': 'aborted:secret_found', 'forbidden': [str(item) for item in captured_forbidden]}
        subprocess.run(['git', 'add', '-A', '--', '.'], cwd=vault_root, env=iso_env, check=True, capture_output=True)
        tree_proc = subprocess.run(['git', 'write-tree'], cwd=vault_root, env=iso_env, check=True, capture_output=True, text=True)
        tree_sha = tree_proc.stdout.strip()
        tree_safe, tree_forbidden = scan_git_tree_for_secrets(vault_root, tree_sha)
        if not tree_safe:
            return {'status': 'aborted:secret_found', 'forbidden': [str(item) for item in tree_forbidden]}
        current_index = live_index.read_bytes() if live_index.is_file() else None
        current_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=vault_root, capture_output=True, text=True, check=False)
        current_parent = current_head.stdout.strip() if current_head.returncode == 0 else ''
        if current_index != user_index_before or current_parent != parent_sha:
            return {'status': 'halted:user_state_changed', 'detail': 'User index or HEAD changed during snapshot; nothing published.'}
        parent_args = ['-p', remote_parent or parent_sha] if (remote_parent or parent_sha) else []
        commit_proc = subprocess.run(['git', 'commit-tree', tree_sha, *parent_args, '-m', f'chore(snapshot): {stamp}'], cwd=vault_root, check=True, capture_output=True, text=True)
        commit_sha = commit_proc.stdout.strip()
        tree_check = subprocess.run(['git', 'rev-parse', f'{commit_sha}^{{tree}}'], cwd=vault_root, check=True, capture_output=True, text=True)
        if tree_check.stdout.strip() != tree_sha:
            return {'status': 'halted:immutable_tree_mismatch', 'detail': 'Commit does not contain the scanned immutable tree.'}
        lease = [f'--force-with-lease=refs/heads/{branch}:{remote_parent}'] if remote_parent else []
        push_proc = subprocess.run(['git', 'push', *lease, remote, f'{commit_sha}:refs/heads/{branch}'], cwd=vault_root, capture_output=True, text=True, check=False, timeout=60)
        if push_proc.returncode != 0:
            return {'status': 'push-failed', 'error': push_proc.stderr}
        remote_proc = subprocess.run(['git', 'ls-remote', remote, f'refs/heads/{branch}'], cwd=vault_root, capture_output=True, text=True, check=False, timeout=60)
        remote_sha = remote_proc.stdout.split()[0] if remote_proc.returncode == 0 and remote_proc.stdout.split() else ''
        if remote_sha != commit_sha:
            return {'status': 'halted:published_ref_mismatch', 'detail': 'Remote ref does not match the verified snapshot commit.'}
        _atomic_write(receipt_file, json.dumps({'ts': now_epoch, 'stamp': stamp, 'remote': remote, 'branch': branch, 'tree': tree_sha, 'commit': commit_sha}, indent=2) + '\n')
        return {'status': 'ok', 'stamp': stamp, 'tree': tree_sha, 'commit': commit_sha}
    except (OSError, subprocess.SubprocessError) as exc:
        return {'status': 'error', 'detail': str(exc)}
    finally:
        isolated_index.unlink(missing_ok=True)


def publish_if_due(
    vault_root: Path,
    remote: str = "origin",
    branch: str = "main",
    min_interval_seconds: int = 3600,
    apply: bool = False,
    *, receipt_file: Path,
) -> dict[str, Any]:
    """Safely commit and push a snapshot if interval has elapsed and no divergence."""
    safe, forbidden = check_secret_guard(vault_root)
    if not safe:
        return {
            "status": "aborted:secret_found",
            "forbidden": forbidden,
        }

    receipt_commit = ''
    if receipt_file.exists():
        try:
            data = json.loads(receipt_file.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError):
            return {'status': 'halted:receipt_invalid', 'detail': 'Snapshot receipt is invalid; fail-closed.'}
        if data.get('remote') != remote or data.get('branch') != branch:
            return {'status': 'halted:receipt_mismatch', 'detail': 'Snapshot receipt belongs to a different remote or branch.'}
        receipt_commit = data.get('commit', '')
        if not isinstance(receipt_commit, str) or not re.fullmatch(r'[0-9a-f]{40}', receipt_commit):
            return {'status': 'halted:receipt_invalid', 'detail': 'Snapshot receipt commit is invalid; fail-closed.'}

    remote_parent = ''
    if receipt_commit:
        remote_parent, remote_error = _remote_ref(vault_root, remote, branch)
        if remote_parent is None:
            return {'status': 'halted:error', 'detail': f'Remote ref could not be read ({remote_error}); fail-closed.'}
        if remote_parent != receipt_commit:
            return {'status': 'halted:remote_changed', 'detail': 'Remote snapshot ref changed outside this publisher; fail-closed.'}

    div_status = _branch_divergence_status(vault_root, remote, branch, receipt_commit=receipt_commit)
    if div_status == "diverged":
        return {"status": "halted:diverged", "detail": "Uzak dal ile yerel commitler çatışıyor; fail-closed duruldu."}
    if div_status in ("error", "unknown"):
        return {"status": f"halted:{div_status}", "detail": f"Uzak dal durumu sorgulanamadı ({div_status}); fail-closed duruldu."}

    now_epoch = time.time()
    if receipt_file.exists():
        try:
            data = json.loads(receipt_file.read_text(encoding="utf-8"))
            last_ts = float(data.get("ts", 0))
            if now_epoch - last_ts < min_interval_seconds:
                return {"status": "skipped:not_due", "seconds_remaining": int(min_interval_seconds - (now_epoch - last_ts))}
        except (OSError, ValueError):
            pass

    if not apply:
        return {
            "status": "preview",
            "vault": str(vault_root),
            "remote": remote,
            "branch": branch,
            "divergence": div_status,
        }

    stamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    return _publish_immutable_snapshot(vault_root, remote, branch, receipt_file, now_epoch, stamp, remote_parent)



def main(argv: list[str] | None = None, *, ctx: AppContext | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, nargs="?", help="Vault kök dizini")
    parser.add_argument("--remote", default="origin", help="Uzak depo adı")
    parser.add_argument("--branch", default="main", help="Hedef dal")
    parser.add_argument("--apply", action="store_true", help="Snapshot'ı sahiden push et")
    args = parser.parse_args(argv)

    if ctx is None:
        raise ValueError("Snapshot publication requires an explicit data context")
    result = publish_if_due(
        vault_root=selected_vault(ctx, args.vault),
        remote=args.remote,
        branch=args.branch,
        apply=args.apply,
        receipt_file=ctx.paths.state_dir / "git-snapshot-receipt.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "preview", "skipped:not_due"} else 1


if __name__ == "__main__":
    sys.exit(main())
