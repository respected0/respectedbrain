# Respot Brain Roadmap, Briefing and Maintenance Design

## Goal

Make a newly opened provider understand the vault without scanning it, generate one reliable
morning briefing per day, and add approval-gated maintenance workflows without weakening Respot's
provider-neutral or single-source architecture.

## Global constraints

- `Core.md` remains human-managed and is never rewritten by automation.
- `.beyin/instructions.md` and `.beyin/skills/*/SKILL.md` remain the only rule and skill sources.
- Claude, Codex, Cursor and Antigravity use the same Python runtime and provider fallback chain.
- No symlink-based installation or runtime design.
- No user note is moved, deleted or edited without explicit approval.
- Windows native and WSL behavior must be exercised on their real runtimes.
- No commit or push without Furkan's explicit approval.

## Slice 1: safe compiler staging and maps

Compile stages are created in the system temporary directory, verified outside the vault, set to
mode `0700` on POSIX, validated with the existing manifest and live-destination boundaries, and
removed on every exit path.

A deterministic `.beyin/map_builder.py` writes two visible, machine-managed files:

- `🎯 100-Command-Center/Vault-Map.md`
- `🎯 100-Command-Center/Skills-Map.md`

The vault map reads paths and small metadata surfaces, excludes git/state/backup/generated adapter
trees, and never bulk-reads note bodies. The skills map reads only canonical
`.beyin/skills/*/SKILL.md` frontmatter. Session start refreshes the maps and injects compact capped
versions before the knowledge index.

## Slice 2: morning briefing

`.beyin/morning_briefing.py --if-due` runs only at or after local 08:00 and only when today's final
briefing does not exist. It collects bounded context from yesterday's daily log, active Threads,
Last Session, Dashboard, Vault Map, the knowledge index and the latest Journal entry. It invokes
the existing provider-neutral `model_runner.py` in text-only mode, validates five required
sections, adds the real preparation timestamp itself and atomically writes
`🎯 100-Command-Center/Briefings/YYYY-MM-DD.md`.

A marked Dashboard block links to today's briefing while preserving all user-owned content.
Failures write health/state, leave no final briefing, release the daily claim and remain retryable.
Concurrent invocations produce one result.

Schedule installation is a separate preview/apply operation requiring explicit approval. Windows
native uses Task Scheduler with `StartWhenAvailable`; WSL uses Task Scheduler invoking `wsl.exe`;
Linux uses a persistent user systemd timer; macOS uses a LaunchAgent with an 08:00 calendar trigger
and login catch-up. Every adapter calls the same `--if-due` worker and embeds no model choice.

## Slice 3: maintenance skills

`beyin-doktor` stays read-only and expands its report to broken links, duplicate candidates, stale
information candidates, pending inbox notes, map freshness, briefing/scheduler health and compiler
health. It emits numbered remediation items containing evidence, affected files, proposed action
and risk; it never applies them.

A canonical `inbox-duzenle` skill reads `📥 000-Inbox/Dump/`, previews title, target folder,
tags, links and rationale per note, then stops for explicit approval. Apply revalidates source
content, refuses target overwrite, touches only approved items and rolls back its batch on error.
Generated Claude and Agents copies continue to come only from the renderer.

## Error handling and observability

All hook and scheduled-job boundaries preserve the current zero-exit contract while recording
machine-readable health. State claims distinguish inflight, success and failure; only a validated
final artifact counts as success. User-authored files are updated only through marked blocks or
approval-gated operations.

## Verification

Each slice starts with a failing regression test. The final gate includes renderer drift, Python
unit/integration tests, shell upgrade tests, PowerShell installer tests, real Windows Python native
tests, WSL execution, `git diff --check`, and an explicit check that no unrelated user change was
overwritten.
