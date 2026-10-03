#!/usr/bin/env python3
"""Render AI-specific adapters from template/.beyin canonical sources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePath, PureWindowsPath
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any, Literal


def _configure_console_output() -> None:
    """Keep Windows OEM consoles from aborting on non-ASCII output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


_configure_console_output()


def _find_repo(start: Path) -> Path:
    resolved = start.resolve()
    for p in (resolved, *resolved.parents):
        if (p / "template").is_dir() and (p / "runtime").is_dir():
            return p
        if (p / ".git").is_dir():
            return p
    if len(resolved.parents) >= 2 and resolved.parents[1].name == "runtime":
        return resolved.parents[2]
    return resolved.parents[1] if len(resolved.parents) >= 2 else resolved


REPO = _find_repo(Path(__file__))
ROOT = REPO
ADAPTERS_DEFAULT = REPO / "runtime" / "adapters" if (REPO / "runtime" / "adapters").is_dir() else (REPO / "template")
TEMPLATE = ADAPTERS_DEFAULT
SOURCE = REPO / "runtime" if (REPO / "runtime" / "instructions.md").is_file() else TEMPLATE / ".beyin"
GENERATED_HEADER = "<!-- GENERATED: edit runtime/instructions.md, then run scripts/render_integrations.py -->\n\n"


def write_text(path: Path, content: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    if check:
        print(path.relative_to(ROOT))
        return True
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
    return True


def write_json(path: Path, payload: dict, check: bool) -> bool:
    return write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        check,
    )


def sync_skills(check: bool) -> bool:
    changed = False
    for destination_root in (
        TEMPLATE / ".claude" / "skills",
        TEMPLATE / ".agents" / "skills",
    ):
        for source_file in sorted((SOURCE / "skills").glob("*/SKILL.md")):
            destination = destination_root / source_file.parent.name / "SKILL.md"
            content = source_file.read_text(encoding="utf-8")
            changed |= write_text(destination, content, check)
    return changed


ProfileName = Literal["portable", "windows-wsl", "windows-native"]
DEFAULT_PYTHON_COMMANDS: dict[str, tuple[str, ...]] = {
    "portable": ("python3",),
    "windows-wsl": ("python3",),
    "windows-native": ("py.exe", "-3"),
}


@dataclass(frozen=True)
class Profile:
    name: ProfileName
    python_command: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.name not in DEFAULT_PYTHON_COMMANDS:
            raise ValueError(f"unsupported-platform:{self.name}")
        if not self.python_command or any(
            not isinstance(part, str) or not part for part in self.python_command
        ):
            raise ValueError("python-command-invalid")


def bridge_argv(
    profile: Profile,
    vault: PurePath,
    provider: str,
    event: str,
    global_hook: bool = False,
) -> list[str]:
    suffix = ["--provider", provider, "--event", event]
    if global_hook:
        suffix.append("--global-hook")
        runtime_bridge = None
        try:
            from runtime_hub import get_runtime_dir
            rdir = get_runtime_dir()
            if (rdir / "hooks" / "bridge.py").is_file():
                runtime_bridge = rdir / "hooks" / "bridge.py"
        except Exception:
            pass
        if not runtime_bridge:
            repo_bridge = Path(__file__).resolve().parent.parent / "runtime" / "hooks" / "bridge.py"
            if repo_bridge.is_file():
                runtime_bridge = repo_bridge

        is_pure_vault = False
        try:
            is_pure_vault = (Path(vault) / ".respected.json").is_file()
        except Exception:
            pass

        if is_pure_vault and runtime_bridge and not (Path(vault) / ".beyin" / "hooks" / "bridge.py").is_file():
            suffix.extend(["--vault", str(vault)])
            if profile.name == "windows-native":
                return [*profile.python_command, str(runtime_bridge), *suffix]
            bridge_str = runtime_bridge.as_posix() if profile.name == "portable" else str(runtime_bridge)
            return [*profile.python_command, bridge_str, *suffix]

    if profile.name == "windows-native":
        bridge = vault / ".beyin" / "hooks" / "bridge.py"
        return [*profile.python_command, str(bridge), *suffix]
    if profile.name == "windows-wsl":
        wsl_cd = vault.as_posix()
        if len(wsl_cd) >= 2 and wsl_cd[1] == ":":
            drive = wsl_cd[0].lower()
            rest = wsl_cd[2:].lstrip("/")
            wsl_cd = f"/mnt/{drive}/{rest}"
        return [
            "wsl.exe",
            "--cd",
            wsl_cd,
            *profile.python_command,
            ".beyin/hooks/bridge.py",
            *suffix,
        ]
    bridge = vault / ".beyin" / "hooks" / "bridge.py" if global_hook else PurePath(
        ".beyin/hooks/bridge.py"
    )
    bridge_str = bridge.as_posix() if profile.name == "portable" else str(bridge)
    return [*profile.python_command, bridge_str, *suffix]


def command_text(
    profile: Profile,
    vault: PurePath,
    provider: str,
    event: str,
    global_hook: bool = False,
) -> str:
    argv = bridge_argv(profile, vault, provider, event, global_hook)
    if profile.name.startswith("windows-"):
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def antigravity_project_command(profile: Profile, event: str) -> str:
    """Render a workspace hook relative to the ``.agents`` config directory.

    Antigravity executes JSON hook commands without Windows shell quote parsing and
    resolves script arguments relative to ``.agents``.  Keeping the bridge path
    relative avoids turning a quoted, spaced vault path into multiple arguments.
    """
    suffix = ["--provider", "antigravity", "--event", event]
    if profile.name == "windows-native":
        argv = [
            *profile.python_command,
            str(PureWindowsPath("..") / ".beyin" / "hooks" / "bridge.py"),
            *suffix,
        ]
        return subprocess.list2cmdline(argv)
    if profile.name == "windows-wsl":
        argv = [
            "wsl.exe",
            "--cd",
            "..",
            *profile.python_command,
            ".beyin/hooks/bridge.py",
            *suffix,
        ]
        return subprocess.list2cmdline(argv)
    return shlex.join(
        [*profile.python_command, "../.beyin/hooks/bridge.py", *suffix]
    )


def _load_config() -> dict[str, Any]:
    if (TEMPLATE / ".beyin" / "config.json").is_file():
        path = TEMPLATE / ".beyin" / "config.json"
    else:
        path = SOURCE / "config.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve_profile(
    platform: str | None,
    python_command: list[str] | None,
    config: dict[str, Any],
) -> Profile:
    selected = platform or config.get("platform") or "portable"
    if selected not in DEFAULT_PYTHON_COMMANDS:
        raise ValueError(f"unsupported-platform:{selected}")
    persisted = config.get("python_command")
    if python_command is not None:
        command = tuple(python_command)
    elif platform is None and isinstance(persisted, list):
        command = tuple(persisted)
    else:
        command = DEFAULT_PYTHON_COMMANDS[selected]
    return Profile(selected, command)


def _claude_settings(profile: Profile) -> dict[str, Any]:
    events = {
        "SessionStart": ("start", "session-start.sh", 15),
        "UserPromptSubmit": ("prompt", "prompt-counter.sh", 5),
        "SessionEnd": ("end", "session-end.sh", 10),
        "PreCompact": ("precompact", "pre-compact.sh", 10),
    }
    hooks: dict[str, Any] = {}
    for event_name, (event, script, timeout) in events.items():
        if profile.name == "windows-native":
            command = command_text(profile, TEMPLATE, "claude", event)
        else:
            command = f'"$CLAUDE_PROJECT_DIR/.claude/hooks/{script}"'
        hooks[event_name] = [
            {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
        ]
    turn_command = command_text(profile, TEMPLATE, "claude", "turn")
    hooks["Stop"] = [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": turn_command,
                    "timeout": 10,
                    "async": True,
                }
            ]
        }
    ]
    return {"hooks": hooks}


def _gemini_settings(profile: Profile) -> dict[str, Any]:
    events = {
        "SessionStart": ("start", 15000),
        "BeforeAgent": ("prompt", 5000),
        "AfterAgent": ("turn", 10000),
        "SessionEnd": ("end", 10000),
        "PreCompress": ("precompact", 10000),
    }
    hooks: dict[str, Any] = {}
    for event_name, (event, timeout) in events.items():
        hooks[event_name] = [
            {
                "hooks": [
                    {
                        "name": f"respected-brain-{event_name.lower()}",
                        "type": "command",
                        "command": command_text(profile, TEMPLATE, "gemini", event),
                        "timeout": timeout,
                        "description": "Sync Respected Brain memory",
                    }
                ]
            }
        ]
    return {"hooks": hooks}


def _extract_vault_identity(vault: Path) -> dict[str, str]:
    replacements: dict[str, str] = {}

    # 1. Try reading identity from structured config files
    respected_json = vault / ".respected.json"
    if respected_json.is_file():
        try:
            rdata = json.loads(respected_json.read_text(encoding="utf-8"))
            if isinstance(rdata, dict):
                if rdata.get("user_name") and "{{" not in str(rdata["user_name"]):
                    replacements.setdefault("{{" + "USER_NAME" + "}}", str(rdata["user_name"]).strip())
                if rdata.get("companion") and "{{" not in str(rdata["companion"]):
                    replacements.setdefault("{{" + "COMPANION" + "}}", str(rdata["companion"]).strip())
                if rdata.get("os_name") and "{{" not in str(rdata["os_name"]):
                    replacements.setdefault("{{" + "OS_NAME" + "}}", str(rdata["os_name"]).strip())
        except Exception:
            pass

    beyin_json = vault / ".beyin" / "config.json"
    if beyin_json.is_file():
        try:
            bdata = json.loads(beyin_json.read_text(encoding="utf-8"))
            if isinstance(bdata, dict):
                if bdata.get("user_name") and "{{" not in str(bdata["user_name"]):
                    replacements.setdefault("{{" + "USER_NAME" + "}}", str(bdata["user_name"]).strip())
                if bdata.get("companion") and "{{" not in str(bdata["companion"]):
                    replacements.setdefault("{{" + "COMPANION" + "}}", str(bdata["companion"]).strip())
                if bdata.get("companion_name") and "{{" not in str(bdata["companion_name"]):
                    replacements.setdefault("{{" + "COMPANION" + "}}", str(bdata["companion_name"]).strip())
        except Exception:
            pass

    # 2. Extract from markdown identity anchors
    candidates = (
        vault / "AGENTS.md",
        vault / "CLAUDE.md",
        vault / ".gemini" / "GEMINI.md",
        vault / ".beyin" / "instructions.md",
        vault / "🔮 850-Companion" / "Kurallar.md",
        vault / "🔮 850-Companion" / "Core.md",
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
                m_os = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                if m_os and "{{" not in m_os.group(1):
                    replacements.setdefault("{{" + "OS_NAME" + "}}", m_os.group(1).strip())
                m_comp = re.search(r"Sen\s+([^,]+),\s+(.+?)\s+için", text)
                if m_comp:
                    if "{{" not in m_comp.group(1):
                        replacements.setdefault("{{" + "COMPANION" + "}}", m_comp.group(1).strip())
                    if "{{" not in m_comp.group(2):
                        replacements.setdefault("{{" + "USER_NAME" + "}}", m_comp.group(2).strip())
                m_user = re.search(r"Kullanıcı:\s*(.+?)\.\s*Bağlam:\s*(.+)$", text, re.MULTILINE)
                if m_user:
                    if "{{" not in m_user.group(1):
                        replacements.setdefault("{{" + "USER_NAME" + "}}", m_user.group(1).strip())
                    if "{{" not in m_user.group(2):
                        replacements.setdefault("{{" + "USER_BIO" + "}}", m_user.group(2).strip())
                m_bio = re.search(r"Bağlam:\s*(.+)$", text, re.MULTILINE)
            except OSError:
                pass
    defaults = {
        "{{" + "OS_NAME" + "}}": "RespectedOS",
        "{{" + "COMPANION" + "}}": "Jarvis",
        "{{" + "USER_NAME" + "}}": "User",
        "{{" + "USER_BIO" + "}}": "Software Engineer & Builder",
        "{{" + "VAULT_PATH" + "}}": str(vault),
    }
    for k, v in defaults.items():
        replacements.setdefault(k, v)
    return replacements


def render(check: bool, profile: Profile) -> bool:
    instructions = (SOURCE / "instructions.md").read_text(encoding="utf-8")
    if "{{" in instructions:
        replacements = _extract_vault_identity(TEMPLATE)
        for key, value in replacements.items():
            instructions = instructions.replace(key, value)
    generated = GENERATED_HEADER + instructions
    changed = False
    if TEMPLATE != REPO and TEMPLATE != (REPO / "runtime" / "adapters"):
        config = _load_config()
        config["platform"] = profile.name
        config["python_command"] = list(profile.python_command)
        target_config = TEMPLATE / ".beyin" / "config.json"
        changed |= write_json(target_config, config, check)
    for path in (TEMPLATE / "AGENTS.md", TEMPLATE / "CLAUDE.md", TEMPLATE / ".gemini" / "GEMINI.md"):
        changed |= write_text(path, generated, check)
    changed |= write_text(
        TEMPLATE / ".agents" / "rules" / "beyin.md",
        generated,
        check,
    )
    changed |= write_text(
        TEMPLATE / ".cursor" / "rules" / "beyin.mdc",
        "---\ndescription: Respected Brain ortak hafıza ve çalışma kuralları\nalwaysApply: true\n---\n\n"
        + generated,
        check,
    )
    changed |= sync_skills(check)
    changed |= write_json(TEMPLATE / ".claude" / "settings.json", _claude_settings(profile), check)
    changed |= write_json(TEMPLATE / ".gemini" / "settings.json", _gemini_settings(profile), check)

    portable = Profile("portable", DEFAULT_PYTHON_COMMANDS["portable"])
    legacy_windows = Profile("windows-wsl", DEFAULT_PYTHON_COMMANDS["windows-wsl"])

    def codex_commands(event: str) -> tuple[str, str]:
        if profile.name == "windows-native":
            native = command_text(profile, TEMPLATE, "codex", event)
            return native, native
        command = command_text(portable, TEMPLATE, "codex", event)
        windows_root: PurePath = TEMPLATE if profile.name == "windows-wsl" else Path(".")
        command_windows = command_text(legacy_windows, windows_root, "codex", event)
        return command, command_windows

    codex_start, codex_start_windows = codex_commands("start")
    codex_prompt, codex_prompt_windows = codex_commands("prompt")
    codex_end, codex_end_windows = codex_commands("end")
    codex_turn, codex_turn_windows = codex_commands("turn")
    codex_precompact, codex_precompact_windows = codex_commands("precompact")

    codex_hooks = {
        "description": "Respected Brain çoklu-AI hafıza kancaları (üretilmiştir).",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": codex_start, "commandWindows": codex_start_windows, "timeout": 15, "additionalContextLimit": 16000}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": codex_prompt, "commandWindows": codex_prompt_windows, "timeout": 5}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": codex_end, "commandWindows": codex_end_windows, "timeout": 10}]}],
            "Stop": [{"hooks": [{"type": "command", "command": codex_turn, "commandWindows": codex_turn_windows, "timeout": 10}]}],
            "PreCompact": [{"hooks": [{"type": "command", "command": codex_precompact, "commandWindows": codex_precompact_windows, "timeout": 10}]}],
        },
    }
    changed |= write_json(TEMPLATE / ".codex" / "hooks.json", codex_hooks, check)

    cursor_hooks = {
        "version": 1,
        "hooks": {
            "sessionStart": [{"command": command_text(profile, TEMPLATE, "cursor", "start"), "timeout": 15}],
            "beforeSubmitPrompt": [{"command": command_text(profile, TEMPLATE, "cursor", "prompt"), "timeout": 5}],
            "sessionEnd": [{"command": command_text(profile, TEMPLATE, "cursor", "end"), "timeout": 10}],
            "preCompact": [{"command": command_text(profile, TEMPLATE, "cursor", "precompact"), "timeout": 10}],
            "afterAgentResponse": [{"command": command_text(profile, TEMPLATE, "cursor", "turn"), "timeout": 10}],
        },
    }
    changed |= write_json(TEMPLATE / ".cursor" / "hooks.json", cursor_hooks, check)

    antigravity_hooks = {
        "respected-brain": {
            "PreInvocation": [{"type": "command", "command": antigravity_project_command(profile, "start"), "timeout": 15}],
            "Stop": [{"type": "command", "command": antigravity_project_command(profile, "turn"), "timeout": 10}],
        }
    }
    changed |= write_json(TEMPLATE / ".agents" / "hooks.json", antigravity_hooks, check)
    return changed


def main() -> int:
    global ROOT, TEMPLATE, SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="değişiklik yapmadan drift raporla")
    parser.add_argument("--root", type=Path, help="template yerine doğrudan bir vault üret")
    parser.add_argument(
        "--platform",
        choices=tuple(DEFAULT_PYTHON_COMMANDS),
        help="Cursor/Antigravity hook komutlarının çalışacağı ortam",
    )
    parser.add_argument(
        "--python-command",
        nargs="+",
        help="seçili profil için güvenilir Python argv bileşenleri",
    )
    parser.add_argument("--source", type=Path, help="talimat ve skill SSOT kaynağı")
    args = parser.parse_args()
    if args.source and (args.source / "instructions.md").is_file():
        SOURCE = args.source.resolve()
        if args.root:
            TEMPLATE = args.root.expanduser().resolve()
            ROOT = TEMPLATE
        else:
            TEMPLATE = REPO / "runtime" / "adapters" if (REPO / "runtime" / "adapters").is_dir() else (REPO / "template")
            ROOT = REPO
    elif args.root:
        TEMPLATE = args.root.expanduser().resolve()
        ROOT = TEMPLATE
        if (TEMPLATE / ".beyin" / "instructions.md").is_file():
            SOURCE = TEMPLATE / ".beyin"
        elif (REPO / "runtime" / "instructions.md").is_file():
            SOURCE = REPO / "runtime"
        else:
            found = False
            for p in Path(__file__).resolve().parents:
                if (p / "runtime" / "instructions.md").is_file():
                    SOURCE = p / "runtime"
                    found = True
                    break
            if not found:
                try:
                    from runtime_hub import get_runtime_dir
                    rdir = get_runtime_dir()
                    if (rdir / "instructions.md").is_file():
                        SOURCE = rdir
                        found = True
                except Exception:
                    pass
    else:
        TEMPLATE = REPO / "runtime" / "adapters" if (REPO / "runtime" / "adapters").is_dir() else (REPO / "template")
        ROOT = REPO
        SOURCE = REPO / "runtime" if (REPO / "runtime" / "instructions.md").is_file() else TEMPLATE / ".beyin"
    if not (SOURCE / "instructions.md").is_file():
        parser.error("instructions.md bulunamadı")
    try:
        profile = resolve_profile(args.platform, args.python_command, _load_config())
    except ValueError as error:
        parser.error(str(error))
    changed = render(args.check, profile)
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
