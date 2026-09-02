# Respected Brain 1.3.0 Full Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for every implementation task and `superpowers:verification-before-completion` before claiming completion. Execute inline in this checkout unless Furkan explicitly requests delegated/subagent execution.

**Goal:** Rename every current product and technical namespace from Respot Brain to Respected Brain, ship a lossless `1.2.0 -> 1.3.0` migration, and leave legacy names visible only in one compatibility module, migration fixtures, and explicitly allowlisted historical records.

**Architecture:** Keep `.beyin` as the provider-neutral canonical rules/skills/runtime source. Put every old identifier in `scripts/legacy_names.py`; fresh installs and generated adapters use only the new namespace. Treat vault files, global provider configuration, and platform scheduler definitions as three separate transactional migration boundaries so each can preview, validate, roll back, and be tested independently.

**Tech stack:** Python 3 standard library, Bash, PowerShell 5.1+, Windows Task Scheduler, systemd user timers, macOS launchd, Markdown, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-02-respected-brain-rename-design.md`

## Global constraints

- Preserve Claude, Codex, Cursor and Antigravity compatibility and the current provider fallback order.
- Preserve `.beyin` as the single source for generated rules and skills; do not hand-edit generated copies.
- Do not introduce symlinks.
- Do not rewrite human-managed memory such as `Core.md`, `Journal.md`, `Threads.md`, daily logs or project notes.
- Use RED -> GREEN -> REFACTOR. Record the focused failing assertion before implementation.
- Legacy literals are allowed only in `scripts/legacy_names.py`, migration test fixtures, the approved rename spec, and explicitly historical upstream/plan records.
- A legacy file is removed only after ownership and path-boundary validation. Unknown files fail closed.
- Commit, current-fork push, fork-network detachment, GitHub repository rename, remote URL change and final push are separate approval gates. Every commit command below is a checkpoint; do not run it without Furkan's explicit approval.
- Do not implement the approved `1.4.0` upstream backlog in this plan.

## Target contracts

```python
# scripts/legacy_names.py
LEGACY_PRODUCT_NAME = "Res" + "pot Brain"
LEGACY_NAMESPACE = "res" + "pot"
LEGACY_GLOBAL_BEGIN = "<!-- " + "RESPOT" + "-GLOBAL:BEGIN -->"
LEGACY_GLOBAL_END = "<!-- " + "RESPOT" + "-GLOBAL:END -->"
LEGACY_HOOK_NAME = LEGACY_NAMESPACE + "-brain"
LEGACY_CURSOR_RULE = LEGACY_HOOK_NAME + ".mdc"
LEGACY_UPDATE_SCRIPT = "scripts/update_" + LEGACY_NAMESPACE + ".py"
LEGACY_MANIFEST_SCRIPT = "scripts/" + LEGACY_NAMESPACE + "_manifest.py"
LEGACY_TASK_PREFIX = LEGACY_NAMESPACE + "-morning-briefing-"
```

The concatenation is intentional: the repository-wide naming contract can prohibit a contiguous old brand literal outside historical allowlists while runtime migration still recognizes it.

```python
# scripts/respected_manifest.py
CORE_VERSION = "2.0.0"
MULTI_VERSION = "1.3.0"
UPDATABLE_MULTI_VERSIONS = ("1.0.0", "1.1.0", "1.2.0", MULTI_VERSION)
```

Fresh/current identifiers:

- product: `Respected Brain`
- repository: `respectedbrain`
- namespace/environment prefix: `respected` / `RESPECTED`
- global block: `RESPECTED-GLOBAL`
- global hook/rule: `respected-brain` / `respected-brain.mdc`
- backup roots: `.respected-backups` and `.respected/schedule-backups`
- scheduler prefix: `respected-morning-briefing-`
- updater/manifest: `update_respected.py` / `respected_manifest.py`

---

### Task 1: Lock the naming contract before renaming code

**Files:**

- Create: `tests/naming_contract_test.py`
- Create: `scripts/legacy_names.py`
- Rename: `scripts/respot_manifest.py` -> `scripts/respected_manifest.py`
- Rename: `tests/update_respot_test.py` -> `tests/update_respected_test.py`
- Rename later in Task 5: `scripts/update_respot.py` -> `scripts/update_respected.py`

**Interfaces:** `find_forbidden_occurrences(root: Path) -> list[tuple[Path, int, str]]`; legacy constants above; manifest exports retain their existing meanings.

- [ ] Add scanner tests against temporary tracked-file fixtures with a fixed current-surface allowlist. Decode text as UTF-8 and reject contiguous `Respot`, `RESPOT`, `respot`, old repository slug, old backup roots and old task prefix outside:

  ```python
  LEGACY_ALLOWLIST = {
      Path("scripts/legacy_names.py"),
      Path("tests/naming_contract_test.py"),
      Path("tests/update_respected_test.py"),
      Path("tests/fixtures/v1_vault.sh"),
      Path("docs/superpowers/plans/2026-08-28-provider-neutral-windows-native.md"),
      Path("docs/superpowers/plans/2026-08-31-roadmap-briefing-maintenance.md"),
      Path("docs/superpowers/plans/2026-09-02-respected-brain-rename.md"),
      Path("docs/superpowers/specs/2026-08-28-provider-neutral-windows-native-design.md"),
      Path("docs/superpowers/specs/2026-08-31-roadmap-briefing-maintenance-design.md"),
      Path("docs/superpowers/specs/2026-09-02-respected-brain-rename-design.md"),
      Path("docs/UPSTREAM-SYNC.md"),
  }
  ```

- [ ] Keep the scanner fixture tests GREEN during Tasks 1-6. In Task 7, activate the same scanner against real tracked executable filenames, public setup files, `template/`, generated adapters and user-visible command output.
- [ ] Add a manifest test requiring `MULTI_VERSION == "1.3.0"`, all three prior stamped versions to be updatable, and no legacy updater/manifest path in the current `RUNTIME` tuple.
- [ ] Run the RED test and preserve the failure showing current old-brand occurrences:

  ```bash
  python3 -m unittest -v tests.naming_contract_test
  ```

- [ ] Create `legacy_names.py`, rename the manifest and updater test with `git mv`, update the test import to `respected_manifest`, and set the target version contract to `1.3.0`.
- [ ] Make the focused manifest and scanner fixture tests GREEN. The repository-wide assertion is intentionally activated only in Task 7, after current production/docs surfaces have been migrated.
- [ ] Run the manifest-focused test and existing suite imports:

  ```bash
  python3 -m unittest -v tests.naming_contract_test tests.update_respected_test
  ```

- [ ] Approval checkpoint only: `git add scripts/legacy_names.py scripts/respected_manifest.py tests/naming_contract_test.py tests/update_respected_test.py && git commit -m "test: define Respected Brain naming contract"`

---

### Task 2: Rename canonical runtime output and generated integrations

**Files:**

- Modify: `scripts/render_integrations.py`
- Modify: `template/.beyin/hooks/bridge.py`
- Modify: `template/.beyin/hooks/lifecycle.py`
- Modify: `template/.beyin/map_builder.py`
- Modify: `template/.beyin/morning_briefing.py`
- Modify: `template/.beyin/runtime_platform.py`
- Modify: `template/.claude/scripts/compile.py`
- Modify: `template/.claude/scripts/flush.py`
- Modify: `template/.agents/hooks.json`
- Modify generated files under `template/.agents/`, `template/.claude/`, `template/.codex/`, `template/.cursor/`
- Modify: `tests/multiai_test.py`, `tests/lifecycle_test.py`, `tests/maps_test.py`, `tests/morning_briefing_test.py`, `tests/profile_render_test.py`, `tests/runtime_platform_test.py`, `tests/scripts_test.py`, `tests/windows_native_test.py`

**Interfaces:** rendering CLI remains `render_integrations.py --root VAULT [--profile PROFILE] [--check]`; briefing marker becomes `RESPECTED-BRIEFING`; generated hook key becomes `respected-brain`.

- [ ] First change assertions to require new generated headers, hook key, marker names, temporary prefixes, state keys and user-facing output. Add a regression that an existing Dashboard containing the legacy briefing marker is readable and is converted to exactly one current block only after a successful refresh.
- [ ] Add a generated-drift assertion that canonical skills in `.beyin/skills/*/SKILL.md` stay byte-identical to `.claude/skills` and `.agents/skills` copies.
- [ ] Run RED tests:

  ```bash
  python3 -m unittest -v tests.multiai_test tests.lifecycle_test tests.maps_test tests.morning_briefing_test tests.profile_render_test tests.runtime_platform_test tests.scripts_test
  ```

- [ ] Replace current runtime identifiers with `Respected Brain`, `respected` and `RESPECTED`. Import legacy briefing constants only where a migration read is required; never make a provider-specific runtime branch.
- [ ] Update `render_integrations.py` so every profile emits `respected-brain` while retaining one canonical `.beyin/instructions.md` and canonical skills source.
- [ ] Run the renderer rather than editing generated adapters independently:

  ```bash
  python3 scripts/render_integrations.py --root template --platform portable
  python3 scripts/render_integrations.py --root template --check
  ```

- [ ] Re-run the focused suite and confirm fresh generated files contain no current old-brand literal outside the migration allowlist.
- [ ] Approval checkpoint only: `git add scripts/render_integrations.py template tests && git commit -m "refactor: rename provider-neutral runtime to Respected Brain"`

---

### Task 3: Make global provider installation migrate old identities safely

**Files:**

- Modify: `scripts/install_global.py`
- Modify: `scripts/install_antigravity_global.py`
- Modify generated template copies through `scripts/render_integrations.py`
- Modify: `tests/multiai_test.py`
- Create: `tests/global_brand_migration_test.py`

**Interfaces:**

```python
def classify_managed_block(existing: str) -> Literal[
    "none", "legacy", "current", "collision", "partial"
]: ...

def build(vault: Path, home: Path, providers: tuple[str, ...], platform: str) \
        -> tuple[list[tuple[Path, str]], list[Path]]: ...
```

- [ ] Add RED fixtures for Claude, Codex, Cursor and Antigravity containing unrelated settings plus legacy managed blocks/hooks/rules.
- [ ] Assert preview leaves the home tree byte-identical; apply migrates one legacy block to one current block; repeat apply is byte-idempotent except for no newly-created backup.
- [ ] Assert legacy+current collision, half marker pairs and a legacy-named Cursor rule without a verifiable managed marker all fail closed without writes.
- [ ] Assert a legacy backup root is never deleted or merged automatically. If both backup roots exist, preview reports a conflict and apply requires a separate explicit migration decision.
- [ ] Run RED tests:

  ```bash
  python3 -m unittest -v tests.global_brand_migration_test tests.multiai_test
  ```

- [ ] Implement block classification using current constants plus imports from `legacy_names.py`. Build the complete write/delete plan before mutating any target.
- [ ] Write backups under `~/.respected-backups/<timestamp>/`; verify every target remains below the selected provider config root and reject symlinks/reparse points.
- [ ] Replace the Antigravity legacy hook only after the new payload validates; preserve unrelated hooks. Remove the old Cursor rule only when its managed contents validate.
- [ ] On any apply failure restore every touched file and leave legacy identities intact; report the backup path.
- [ ] Regenerate template script copies and run drift checks.
- [ ] Approval checkpoint only: `git add scripts/install_global.py scripts/install_antigravity_global.py scripts/render_integrations.py template/scripts tests/global_brand_migration_test.py tests/multiai_test.py && git commit -m "feat: migrate global identities to Respected Brain"`

---

### Task 4: Transactionally migrate briefing schedules on every platform

**Files:**

- Modify: `scripts/install_briefing_schedule.py`
- Modify generated: `template/scripts/install_briefing_schedule.py`
- Modify: `tests/briefing_schedule_test.py`
- Modify: `tests/windows_native_test.py`
- Create: `tests/briefing_schedule_windows_test.ps1`

**Interfaces:** `_identifier(vault) -> respected-morning-briefing-<digest>`; `_legacy_identifier(vault)` derives the old prefix from `legacy_names.py`; scheduler command execution captures bytes before platform decoding.

- [ ] Add RED unit tests for current identifiers and `.respected/schedule-backups`, and for a same-vault legacy definition discovered on Windows, systemd and launchd.
- [ ] Model the migration order with mocks and assert exact calls: query both -> backup legacy -> create current -> query/verify current -> delete legacy. Inject failure at create, verification and delete; require rollback to the original legacy definition.
- [ ] Add a byte-output regression with Turkish OEM text encoded as `cp857`. It must decode without raising and retain diagnostic text:

  ```python
  encoded = "Görev başarıyla oluşturuldu".encode("cp857")
  self.assertIn("Görev", decode_windows_output(encoded))
  ```

- [ ] Add native PowerShell coverage that creates a uniquely named disposable test task, queries it, verifies the new definition and removes it in `finally`. The test must skip with an explicit reason when Task Scheduler access is unavailable.
- [ ] Run RED tests:

  ```bash
  python3 -m unittest -v tests.briefing_schedule_test
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/briefing_schedule_windows_test.ps1
  ```

- [ ] Change subprocess handling from `text=True` to bytes for Windows commands; decode with the detected console code page, then `cp857`, then UTF-8 with a diagnostic-preserving fallback. Do not decode XML payloads through the console encoding; read exported XML as bytes and honor its declaration/BOM.
- [ ] Implement create-before-delete verification and restore. Keep preview mutation-free and provider-free; retain `--if-due` as the single worker entry point.
- [ ] Implement the same identity transition for systemd user units and LaunchAgents, with backups outside the vault and idempotent repeat apply.
- [ ] Regenerate the template copy and rerun focused plus real WSL-to-Windows tests.
- [ ] Approval checkpoint only: `git add scripts/install_briefing_schedule.py template/scripts/install_briefing_schedule.py tests/briefing_schedule_test.py tests/briefing_schedule_windows_test.ps1 tests/windows_native_test.py && git commit -m "feat: migrate Respected Brain briefing schedules"`

---

### Task 5: Rename and harden the transactional vault updater

**Files:**

- Rename: `scripts/update_respot.py` -> `scripts/update_respected.py`
- Modify: `scripts/respected_manifest.py`
- Modify: `tests/update_respected_test.py`
- Modify: `tests/fixtures/v1_vault.sh`
- Modify: `tests/upgrade_transaction_test.sh`
- Modify: `tests/upgrade_settings_test.sh`

**Interfaces:** CLI remains `update_respected.py VAULT [--platform auto|portable|windows-wsl|windows-native] [--apply]`; accepts stamps `1.0.0`, `1.1.0`, `1.2.0`; returns `3` only for already-current `1.3.0`.

- [ ] Build a personalized `1.2.0` fixture containing byte snapshots of `Core.md`, `Journal.md`, `Threads.md`, daily notes and a user project; include both legacy managed scripts and an unrelated similarly named file.
- [ ] Add RED assertions that preview changes nothing, apply writes `1.3.0`, installs only current managed scripts, removes only ownership-validated legacy updater/manifest files, and preserves all human files byte-for-byte.
- [ ] Add failure injection through `RESPECTED_TEST_FAIL_GATE=render`; verify managed files, deleted legacy files, config and version stamp all return byte-for-byte to their original state.
- [ ] Add boundary tests rejecting root paths, vault-contained transaction staging/backups, symlink/reparse-point managed targets and a legacy file whose content/hash does not match a known managed form.
- [ ] Run RED tests:

  ```bash
  python3 -m unittest -v tests.update_respected_test
  bash tests/upgrade_transaction_test.sh
  bash tests/upgrade_settings_test.sh
  ```

- [ ] Import every legacy path from `legacy_names.py`. Expand the transaction manifest to record current managed paths, validated legacy removals, existence, hashes and modes before any write.
- [ ] Stage outside the vault using a randomly named system-temp directory, verify it is outside the resolved vault, set POSIX mode `0700` when applicable, then clean it in `finally` on success and failure.
- [ ] Back up all mutation targets before installing. Promote runtime/generated files, render, run syntax/JSON/placeholder/drift gates, remove validated legacy files, and write `.beyin-multi-version` last.
- [ ] Rename the backup manifest to `respected-update-manifest.json`; leave old backup directories untouched.
- [ ] Re-run focused tests and ensure an already-current vault returns `3` without mutation.
- [ ] Approval checkpoint only: `git add scripts/update_respected.py scripts/respected_manifest.py scripts/legacy_names.py tests/update_respected_test.py tests/fixtures/v1_vault.sh tests/upgrade_transaction_test.sh tests/upgrade_settings_test.sh && git commit -m "feat: add transactional Respected Brain updater"`

---

### Task 6: Update fresh installers and migration shell flow

**Files:**

- Modify: `scripts/upgrade.sh`
- Modify: `scripts/install-windows.ps1`
- Modify: `tests/upgrade_transaction_test.sh`
- Modify: `tests/upgrade_settings_test.sh`
- Modify: `tests/install_windows_test.ps1`
- Modify: `.gitignore`

**Interfaces:** fresh Windows install stamps `2.0.0 / 1.3.0`; test variables use `RESPECTED_TEST_*`; default upgrade backup root becomes `~/.respected-brain-yedek` without moving or deleting the old root.

- [ ] Change PowerShell tests first to require `RESPECTED_TEST_COMMAND_ROOT`, `RESPECTED_TEST_PYTHON`, a `RESPECTED_PYTHON_OK` probe, new product output and `1.3.0` stamp. Add a test proving an old test env variable has no effect on a fresh install.
- [ ] Change shell transaction tests first to require new messages, Git fallback name, backup root and final stamp while retaining v1/core-v2 migration behavior.
- [ ] Run RED platform tests:

  ```bash
  bash tests/upgrade_transaction_test.sh
  bash tests/upgrade_settings_test.sh
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/install_windows_test.ps1
  ```

- [ ] Update `upgrade.sh` and `install-windows.ps1` user-visible branding, variables, temporary names and version checks. Preserve transactional ordering, provider-neutral configuration and the current real-Python resolution logic.
- [ ] Ensure fresh installers copy `update_respected.py`, `respected_manifest.py` and `legacy_names.py`, never the legacy-named scripts.
- [ ] Change `.respot-install-*` ignore entry to `.respected-install-*`; do not add a broad ignore that could hide migration fixtures.
- [ ] Run `bash -n scripts/upgrade.sh`, PowerShell parsing, and the full focused platform tests.
- [ ] Approval checkpoint only: `git add scripts/upgrade.sh scripts/install-windows.ps1 tests/upgrade_transaction_test.sh tests/upgrade_settings_test.sh tests/install_windows_test.ps1 .gitignore && git commit -m "refactor: rename Respected Brain installers"`

---

### Task 7: Rename every current public surface and document migration truthfully

**Files:**

- Modify: `README.md`
- Modify: `SETUP.md`
- Modify: `SETUP-WINDOWS.md`
- Modify: `MULTI_AI.md`
- Modify: `docs/beyin-v2.md`
- Modify: `docs/SPEC-V2.md`
- Modify: `docs/FEATURE-BACKLOG.md`
- Modify: `docs/UPSTREAM-ADOPTION-BACKLOG.md`
- Modify: `docs/UPSTREAM-SYNC.md` only where text is current rather than historical evidence
- Modify: `template/.beyin/instructions.md`, `template/AGENTS.md`, `template/CLAUDE.md`, Command Center generated examples and canonical maintenance skills
- Modify: `tests/multiai_test.py`, `tests/naming_contract_test.py`

**Interfaces:** clone examples use `https://github.com/respected0/respectedbrain.git` and `cd respectedbrain`; update examples call `scripts/update_respected.py`; all version tables report `1.3.0`.

- [ ] Extend public-doc tests to require the four providers, three platform profiles, preview/apply wording, old-vault migration instructions, current schedule/backup names and `1.3.0`.
- [ ] Add negative assertions for old clone URL, old updater command and current-facing old brand text. Historical fork URLs/SHA evidence remain allowlisted and labeled historical.
- [ ] Run RED tests:

  ```bash
  python3 -m unittest -v tests.naming_contract_test tests.multiai_test
  ```

- [ ] Update the public name, repository slug, commands, screenshots/text examples, scheduler paths, environment prefixes and version descriptions. State clearly that `.beyin` names remain for compatibility and are not product branding.
- [ ] Add an upgrade section distinguishing fresh install, stamped `1.0.0/1.1.0/1.2.0` update, damgasız v1 shell upgrade and global/scheduler migration previews.
- [ ] Keep personal vault naming examples user-selectable; do not imply the vault must be named `RespectedOS`.
- [ ] Keep the existing MIT license notice unchanged and add a concise README attribution: Respected Brain began from Avenox Beyin's MIT-licensed history and now develops independently. Link the upstream as historical origin, not as a live fork/sync promise.
- [ ] Update the feature backlog to mark `1.3.0` rename/migration as the current release boundary and the nine approved upstream adaptations as still-unimplemented `1.4.0` work.
- [ ] Render canonical instructions/skills into provider adapters; verify byte identity and the naming contract.
- [ ] Approval checkpoint only: `git add README.md SETUP.md SETUP-WINDOWS.md MULTI_AI.md docs template tests/naming_contract_test.py tests/multiai_test.py && git commit -m "docs: publish Respected Brain 1.3.0 migration"`

---

### Task 8: Complete repository-wide and platform verification

**Files:** modify only defects exposed by the gates; add a regression test before each fix.

- [ ] Run the current-surface scan and inspect every hit. Only explicit migration/history allowlist entries may remain:

  ```bash
  rg --hidden --glob '!.git/**' -n '(Respot|RESPOT|respot|respot-brain|\.respot)' .
  python3 -m unittest -v tests.naming_contract_test
  ```

- [ ] Run generated drift and the complete WSL/Linux Python suite:

  ```bash
  python3 scripts/render_integrations.py --root template --check
  python3 -m unittest discover -s tests -p '*_test.py' -v
  ```

- [ ] Run every shell transaction/hook suite:

  ```bash
  bash tests/hooks_test.sh
  bash tests/upgrade_transaction_test.sh
  bash tests/upgrade_settings_test.sh
  ```

- [ ] Run real Windows PowerShell and native Python gates from WSL:

  ```bash
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/install_windows_test.ps1
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/briefing_schedule_windows_test.ps1
  py.exe -3 -m unittest -v tests.windows_native_test tests.runtime_platform_test
  ```

- [ ] Exercise all three fresh profiles in temporary directories and assert: `1.3.0`, current filenames only, provider-neutral adapters, clean render check, and no symlinks.
- [ ] Exercise a real WSL-managed Windows Task Scheduler migration using a disposable vault/task name; verify a missed-run-safe new task exists and the legacy fixture task is removed only after verification. Clean only the disposable test tasks in `finally`.
- [ ] Verify Git hygiene:

  ```bash
  git diff --check
  git status --short --branch
  git diff --stat
  ```

- [ ] Use `superpowers:requesting-code-review` and address findings with RED tests. Then use `superpowers:verification-before-completion`; do not infer success from an earlier run.
- [ ] Stop and request explicit commit approval. Do not rename GitHub or push in this task.

---

### Task 9: Detach into an independent repository, rename and release

**Files/state:** GitHub repository settings, repository-external verified bundle, local remotes, a disposable clone directory. No source edit should be needed if Task 7 used the final URL.

**Interfaces:** `origin` ends at `git@github.com:respected0/respectedbrain.git`; `avenox-reference` fetches from `https://github.com/avenoxai/avenoxbeyin.git` and has a deliberately invalid push URL.

- [ ] Inspect the GitHub repository before mutation. Record visibility, size, default branch, child-fork eligibility, branch/tag list, Actions variables/secrets names, releases, issues, pull requests, wiki, stars and watchers. Do not print secret values.
- [ ] Explain GitHub's permanent metadata-loss warning and obtain explicit approval for the current fork push. Push only the already-approved, fully verified commits to the current fork and verify remote `main` equals local `HEAD`:

  ```bash
  git push origin main
  test "$(git rev-parse HEAD)" = "$(git ls-remote origin refs/heads/main | cut -f1)"
  ```

- [ ] Create a repository-external, timestamped safety bundle without deleting or modifying repository data, then verify all references:

  ```bash
  backup_dir="$(mktemp -d)"
  git bundle create "$backup_dir/respectedbrain-before-detach.bundle" --all
  git bundle verify "$backup_dir/respectedbrain-before-detach.bundle"
  git show-ref > "$backup_dir/respectedbrain-before-detach.refs"
  ```

- [ ] Report the exact bundle path and recorded refs. Keep the bundle until the independent repository, renamed remote and fresh clone have all been verified.
- [ ] Confirm GitHub's direct `Leave fork network` option is available: repository is public, below 1 GB and has no child forks. If any precondition fails, stop; do not delete/recreate the repository automatically.
- [ ] Obtain separate explicit approval immediately before selecting **Settings -> General -> Danger Zone -> Leave fork network**. This approval is single-use and does not authorize rename or deletion.
- [ ] After GitHub completes the operation, verify the repository no longer identifies an upstream/fork parent and that expected `main`, remote branches, tags and Actions workflow files remain. Compare remote refs with `respectedbrain-before-detach.refs`; explain any GitHub-generated ref differences before continuing.
- [ ] Preserve attribution: leave the existing MIT `Copyright (c) 2026 Avenox` notice and commit history intact. Ensure Task 7's README contains a concise origin/independent-development note; do not represent inherited work as newly authored.
- [ ] Obtain separate approval to rename the now-independent GitHub repository to `respectedbrain`. Rename it and verify the canonical page, default branch, branch protection, Actions configuration and final URL.
- [ ] Obtain separate approval before changing local remotes. Apply and verify:

  ```bash
  git remote set-url origin git@github.com:respected0/respectedbrain.git
  git remote rename upstream avenox-reference
  git remote set-url --push avenox-reference DISABLED
  git remote -v
  ```

- [ ] Assert `origin` fetch/push targets only the independent repository and `avenox-reference` can fetch but cannot accidentally receive a push. Fetch both remotes without merging:

  ```bash
  git fetch --prune origin
  git fetch --prune avenox-reference
  ```

- [ ] Clone `https://github.com/respected0/respectedbrain.git` into a fresh `mktemp -d` directory. From that clone run:

  ```bash
  python3 -m unittest -v tests.naming_contract_test
  python3 scripts/render_integrations.py --root template --check
  git status --short --branch
  ```

- [ ] Run the documented fresh-install preview for all three profiles from the disposable clone; confirm the README resolves only canonical URLs and the clone remains clean.
- [ ] Obtain explicit final push approval only if post-rename changes exist. Push `main`, compare local and remote commit IDs, and report the bundle path plus every verification result.
- [ ] Keep `avenox-reference` solely for deliberate upstream audits. Never automatically merge, rebase or sync it into Respected Brain.

## Definition of done

- Fresh users see only Respected Brain/current namespace on supported public and runtime surfaces.
- A personalized stamped `1.2.0` vault reaches `1.3.0` without any human memory byte changing.
- Global provider configs and scheduler definitions migrate transactionally, preview first, with fail-closed collision behavior.
- Claude, Codex, Cursor and Antigravity remain generated from one provider-neutral source.
- Windows native, real WSL/Task Scheduler, Linux adapter and macOS adapter gates pass.
- No symlink is introduced and no unapproved user data, backup, task or remote state is deleted.
- GitHub shows Respected Brain as an independent repository; the original MIT notice and complete Git history remain, and a verified pre-detach bundle exists outside the repository through final validation.
- The nine approved upstream adaptations remain recorded for `1.4.0`, not silently mixed into this release.
