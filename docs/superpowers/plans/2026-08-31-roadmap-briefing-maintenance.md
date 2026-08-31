# Respot Brain Roadmap, Briefing and Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver secure compiler staging, visible automatic maps, a provider-neutral daily briefing, and approval-gated maintenance workflows.

**Architecture:** Three independently testable vertical slices extend the existing standard-library Python runtime. Generated agent adapters and skills continue to come from `.beyin`; platform schedulers are thin adapters around one briefing worker.

**Tech Stack:** Python 3 standard library, Bash, PowerShell 5.1, Windows Task Scheduler, systemd user timers, macOS launchd, Markdown.

**Spec:** `docs/superpowers/specs/2026-08-31-roadmap-briefing-maintenance-design.md`

## Global Constraints

- Preserve provider neutrality and the current fallback behavior.
- Preserve `.beyin` as the only rule and skill source.
- Do not use symlinks.
- Write tests before implementation.
- Do not commit or push without explicit user approval.

---

### Task 1: Move compile staging outside the vault

**Files:** modify `tests/scripts_test.py` and `template/.claude/scripts/compile.py`.

**Interfaces:** `_prepare_stage(vault_root, state_dir, daily_path)` still returns `(stage, live_baseline)`; only stage ownership and boundary assertions change.

- [ ] Change the compiler success and cleanup tests to require `Path(tempfile.gettempdir())` ancestry, vault exclusion, POSIX `0700`, and cleanup.
- [ ] Run the focused tests and confirm the old `.state` staging implementation fails.
- [ ] Create the random stage in system temp, reject a stage inside the vault, retain `0700`, manifest validation and unconditional cleanup.
- [ ] Run focused WSL tests and real Windows Python tests.

### Task 2: Add deterministic visible maps

**Files:** create `template/.beyin/map_builder.py` and `tests/maps_test.py`; modify `template/.beyin/hooks/lifecycle.py`, `tests/lifecycle_test.py`, `scripts/respot_manifest.py`, renderer/updater tests and template Command Center files.

**Interfaces:** `refresh_maps(vault_root: Path) -> tuple[Path, Path]`; `render_vault_map(vault_root: Path) -> str`; `render_skills_map(vault_root: Path) -> str`.

- [ ] Write tests for deterministic output, excluded roots, canonical-skill-only parsing, atomic writes and untouched `Core.md`.
- [ ] Run them and confirm the module is missing.
- [ ] Implement the map builder with bounded metadata reads and machine-managed headers.
- [ ] Add capped map sections to session-start context and test the 16,000-character limit.
- [ ] Add the runtime file to install/update ownership and verify renderer drift.

### Task 3: Add the briefing worker

**Files:** create `template/.beyin/morning_briefing.py` and `tests/morning_briefing_test.py`; modify `scripts/respot_manifest.py` and updater gates.

**Interfaces:** `run_if_due(vault_root: Path, now: datetime | None = None) -> bool`; final output is `Briefings/YYYY-MM-DD.md` with five required headings.

- [ ] Write failing tests for before-08 no-op, exact headings, real preparation time, existing-output idempotency, failure retry, concurrency and Dashboard marker preservation.
- [ ] Implement bounded source loading, text-only `run_model`, schema validation, locking, claims, atomic final write and health state.
- [ ] Test provider fallback with CLI stubs and confirm the model never receives vault write access.
- [ ] Add the worker to install/update ownership and syntax gates.

### Task 4: Add preview/apply schedule adapters

**Files:** create `scripts/install_briefing_schedule.py`, `template/scripts/install_briefing_schedule.py`, `tests/briefing_schedule_test.py`; modify installer documentation and managed manifests.

**Interfaces:** CLI accepts `vault`, `--platform portable|windows-wsl|windows-native`, and `--apply`; preview performs no writes.

- [ ] Write failing tests for all four rendered scheduler definitions, preview immutability, provider-free commands and spaced vault paths.
- [ ] Implement Task Scheduler, systemd and launchd definitions around `morning_briefing.py --if-due`.
- [ ] Require `--apply`, preserve/backup replaced managed definitions and make repeated apply idempotent.
- [ ] Exercise Windows Task Scheduler rendering through PowerShell and WSL command execution.

### Task 5: Extend maintenance skills

**Files:** modify `template/.beyin/skills/beyin-doktor/SKILL.md`; create `template/.beyin/skills/inbox-duzenle/SKILL.md`; modify `tests/multiai_test.py` and add focused contract tests if needed.

**Interfaces:** doctor remains read-only; inbox workflow requires preview followed by explicit approval and source revalidation.

- [ ] Write failing contract tests for the new doctor checks and inbox approval/rollback rules.
- [ ] Update only canonical skills, then run the renderer to generate provider copies.
- [ ] Verify canonical/generated byte equality and that no skill introduces an automatic mutation path.

### Task 6: Version, documentation and full verification

**Files:** modify version manifest, updater/installers, `README.md`, `SETUP.md`, `SETUP-WINDOWS.md`, `MULTI_AI.md`, `docs/beyin-v2.md`, `docs/FEATURE-BACKLOG.md`, and `docs/UPSTREAM-SYNC.md`.

**Interfaces:** stamped 1.1.0 vaults preview and update transactionally to the new multi-AI version while personal memory survives byte-identically.

- [ ] Add updater tests proving preview immutability, rollback and preservation of personal files.
- [ ] Update setup and technical documentation with maps, briefing schedules, approval gates and honest platform status.
- [ ] Run renderer drift, all Python tests, all shell tests, Windows PowerShell installer tests and real Windows Python native tests.
- [ ] Run `git diff --check` and inspect `git status`; stop without commit or push.
