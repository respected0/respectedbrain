"""Version and managed-file ownership shared by Respected migration tools."""

from __future__ import annotations


CORE_VERSION = "2.0.0"
MULTI_VERSION = "1.4.0"
UPDATABLE_MULTI_VERSIONS = ("1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.3.1", "1.3.2", MULTI_VERSION)

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
    ".beyin/map_builder.py",
    ".beyin/morning_briefing.py",
    ".beyin/hooks/lifecycle.py",
    ".beyin/hooks/bridge.py",
    ".beyin/model_runner.py",
    ".beyin/events.py",
    ".claude/hooks/lib.sh",
    ".claude/hooks/session-start.sh",
    ".claude/hooks/prompt-counter.sh",
    ".claude/hooks/session-end.sh",
    ".claude/hooks/pre-compact.sh",
    ".claude/scripts/flush.py",
    ".claude/scripts/compile.py",
    "scripts/render_integrations.py",
    "scripts/legacy_names.py",
    "scripts/install_antigravity_global.py",
    "scripts/install_global.py",
    "scripts/install_briefing_schedule.py",
    "scripts/set_summary_provider.py",
    "scripts/repair_daily.py",
    "scripts/backup_restic.py",
    "scripts/publish_git_snapshot.py",
    "scripts/arama.py",
    "scripts/vault_mcp_server.py",
    "scripts/mine_agent_history.py",
)

SKILL_DESTINATIONS = (".beyin/skills", ".claude/skills", ".agents/skills")
