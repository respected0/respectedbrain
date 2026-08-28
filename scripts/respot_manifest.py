"""Version and managed-file ownership shared by Respot migration tools."""

from __future__ import annotations


CORE_VERSION = "2.0.0"
MULTI_VERSION = "1.1.0"
UPDATABLE_MULTI_VERSIONS = ("1.0.0", MULTI_VERSION)

GENERATED = (
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/settings.json",
    ".codex/hooks.json",
    ".cursor/hooks.json",
    ".cursor/rules/beyin.mdc",
    ".agents/hooks.json",
    ".agents/rules/beyin.md",
)

RUNTIME = (
    ".beyin/runtime_platform.py",
    ".beyin/hooks/lifecycle.py",
    ".beyin/hooks/bridge.py",
    ".beyin/model_runner.py",
    ".claude/hooks/lib.sh",
    ".claude/hooks/session-start.sh",
    ".claude/hooks/prompt-counter.sh",
    ".claude/hooks/session-end.sh",
    ".claude/hooks/pre-compact.sh",
    ".claude/scripts/flush.py",
    ".claude/scripts/compile.py",
    "scripts/render_integrations.py",
    "scripts/install_antigravity_global.py",
    "scripts/install_global.py",
    "scripts/set_summary_provider.py",
)

SKILL_DESTINATIONS = (".beyin/skills", ".claude/skills", ".agents/skills")
