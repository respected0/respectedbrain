#!/usr/bin/env python3
"""Render AI-specific adapters from template/.beyin canonical sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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


WINDOWS_WSL = False


def command(provider: str, event: str, windows: bool | None = None) -> str:
    use_windows = WINDOWS_WSL if windows is None else windows
    if use_windows:
        wsl_root = TEMPLATE.as_posix() if WINDOWS_WSL else "."
        prefix = f'wsl.exe --cd "{wsl_root}" python3'
    else:
        prefix = "python3"
    return f'{prefix} .beyin/hooks/bridge.py --provider {provider} --event {event}'


def render(check: bool) -> bool:
    instructions = (SOURCE / "instructions.md").read_text(encoding="utf-8")
    generated = GENERATED_HEADER + instructions
    changed = False
    for helper_name in ("render_integrations.py", "install_antigravity_global.py"):
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
        "---\ndescription: Avenox Beyin ortak hafıza ve çalışma kuralları\nalwaysApply: true\n---\n\n"
        + generated,
        check,
    )
    changed |= sync_skills(check)

    codex_hooks = {
        "description": "Avenox Beyin çoklu-AI hafıza kancaları (üretilmiştir).",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": command("codex", "start", False), "commandWindows": command("codex", "start", True), "timeout": 15, "additionalContextLimit": 16000}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": command("codex", "prompt", False), "commandWindows": command("codex", "prompt", True), "timeout": 5}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": command("codex", "end", False), "commandWindows": command("codex", "end", True), "timeout": 3}]}],
            "PreCompact": [{"hooks": [{"type": "command", "command": command("codex", "precompact", False), "commandWindows": command("codex", "precompact", True), "timeout": 10}]}],
        },
    }
    changed |= write_json(TEMPLATE / ".codex" / "hooks.json", codex_hooks, check)

    cursor_hooks = {
        "version": 1,
        "hooks": {
            "sessionStart": [{"command": command("cursor", "start"), "timeout": 15}],
            "beforeSubmitPrompt": [{"command": command("cursor", "prompt"), "timeout": 5}],
            "sessionEnd": [{"command": command("cursor", "end"), "timeout": 10}],
            "preCompact": [{"command": command("cursor", "precompact"), "timeout": 10}],
        },
    }
    changed |= write_json(TEMPLATE / ".cursor" / "hooks.json", cursor_hooks, check)

    antigravity_hooks = {
        "avenox-beyin": {
            "PreInvocation": [{"type": "command", "command": command("antigravity", "start"), "timeout": 15}],
            "Stop": [{"type": "command", "command": command("antigravity", "end"), "timeout": 10}],
        }
    }
    changed |= write_json(TEMPLATE / ".agents" / "hooks.json", antigravity_hooks, check)
    return changed


def main() -> int:
    global ROOT, TEMPLATE, SOURCE, WINDOWS_WSL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="değişiklik yapmadan drift raporla")
    parser.add_argument("--root", type=Path, help="template yerine doğrudan bir vault üret")
    parser.add_argument(
        "--platform",
        choices=("portable", "windows-wsl"),
        default="portable",
        help="Cursor/Antigravity hook komutlarının çalışacağı ortam",
    )
    args = parser.parse_args()
    if args.root:
        TEMPLATE = args.root.expanduser().resolve()
        ROOT = TEMPLATE
        SOURCE = TEMPLATE / ".beyin"
    WINDOWS_WSL = args.platform == "windows-wsl"
    if not (SOURCE / "instructions.md").is_file():
        parser.error("template/.beyin/instructions.md bulunamadı")
    changed = render(args.check)
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
