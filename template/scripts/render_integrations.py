#!/usr/bin/env python3
"""Render AI-specific adapters from template/.beyin canonical sources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path, PurePath
import shlex
import subprocess
from typing import Any, Literal


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO
TEMPLATE = REPO if (REPO / ".beyin" / "instructions.md").is_file() else REPO / "template"
SOURCE = TEMPLATE / ".beyin"
GENERATED_HEADER = "<!-- GENERATED: edit .beyin/instructions.md, then run scripts/render_integrations.py -->\n\n"


def write_text(path: Path, content: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    if check:
        print(path.relative_to(ROOT))
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
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
    if profile.name == "windows-native":
        bridge = vault / ".beyin" / "hooks" / "bridge.py"
        return [*profile.python_command, str(bridge), *suffix]
    if profile.name == "windows-wsl":
        return [
            "wsl.exe",
            "--cd",
            vault.as_posix(),
            *profile.python_command,
            ".beyin/hooks/bridge.py",
            *suffix,
        ]
    bridge = vault / ".beyin" / "hooks" / "bridge.py" if global_hook else PurePath(
        ".beyin/hooks/bridge.py"
    )
    return [*profile.python_command, str(bridge), *suffix]


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


def _load_config() -> dict[str, Any]:
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
    return {"hooks": hooks}


def render(check: bool, profile: Profile) -> bool:
    instructions = (SOURCE / "instructions.md").read_text(encoding="utf-8")
    generated = GENERATED_HEADER + instructions
    changed = False
    config = _load_config()
    config["platform"] = profile.name
    config["python_command"] = list(profile.python_command)
    changed |= write_json(SOURCE / "config.json", config, check)
    for helper_name in (
        "render_integrations.py",
        "install_antigravity_global.py",
        "install_global.py",
        "install_briefing_schedule.py",
        "set_summary_provider.py",
    ):
        helper_source = REPO / "scripts" / helper_name
        helper_target = TEMPLATE / "scripts" / helper_name
        if helper_source.is_file() and helper_source.resolve() != helper_target.resolve():
            changed |= write_text(
                helper_target,
                helper_source.read_text(encoding="utf-8"),
                check,
            )
    for path in (TEMPLATE / "AGENTS.md", TEMPLATE / "CLAUDE.md"):
        changed |= write_text(path, generated, check)
    changed |= write_text(
        TEMPLATE / ".agents" / "rules" / "beyin.md",
        generated,
        check,
    )
    changed |= write_text(
        TEMPLATE / ".cursor" / "rules" / "beyin.mdc",
        "---\ndescription: Respot Brain ortak hafıza ve çalışma kuralları\nalwaysApply: true\n---\n\n"
        + generated,
        check,
    )
    changed |= sync_skills(check)
    changed |= write_json(TEMPLATE / ".claude" / "settings.json", _claude_settings(profile), check)

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
    codex_precompact, codex_precompact_windows = codex_commands("precompact")

    codex_hooks = {
        "description": "Respot Brain çoklu-AI hafıza kancaları (üretilmiştir).",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": codex_start, "commandWindows": codex_start_windows, "timeout": 15, "additionalContextLimit": 16000}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": codex_prompt, "commandWindows": codex_prompt_windows, "timeout": 5}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": codex_end, "commandWindows": codex_end_windows, "timeout": 3}]}],
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
        },
    }
    changed |= write_json(TEMPLATE / ".cursor" / "hooks.json", cursor_hooks, check)

    antigravity_hooks = {
        "respot-brain": {
            "PreInvocation": [{"type": "command", "command": command_text(profile, TEMPLATE, "antigravity", "start"), "timeout": 15}],
            "Stop": [{"type": "command", "command": command_text(profile, TEMPLATE, "antigravity", "end"), "timeout": 10}],
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
    args = parser.parse_args()
    if args.root:
        TEMPLATE = args.root.expanduser().resolve()
        ROOT = TEMPLATE
        SOURCE = TEMPLATE / ".beyin"
    if not (SOURCE / "instructions.md").is_file():
        parser.error("template/.beyin/instructions.md bulunamadı")
    try:
        profile = resolve_profile(args.platform, args.python_command, _load_config())
    except ValueError as error:
        parser.error(str(error))
    changed = render(args.check, profile)
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
