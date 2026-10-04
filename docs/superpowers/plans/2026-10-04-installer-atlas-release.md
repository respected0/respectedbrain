# Installer, Repository Atlas and Publication Implementation Plan

> For agentic workers: use executing-plans with focused independent investigations and a fresh final review. The user authorized this sequence on 2026-10-04.

**Goal:** Preserve GUI setup selections, improve measured installation throughput, explain every project file, audit repository contents and publish verified code to GitHub.

**Architecture:** Keep the approved src package, immutable application / technical data / user vault boundaries and schema 3 recovery contract. Forward explicit selections into existing wizard defaults. Optimize redundant journal work while retaining durable write-ahead records, hashes, permissions and compare-and-swap rollback. Generate the atlas from an annotated inventory and check drift in CI.

**Tech Stack:** Python >=3.10 stdlib, unittest, Tkinter, PyInstaller, Inno Setup, GitHub Actions.

**Spec:** User request in this chat (2026-10-04); approved modular foundation specification and plan in this directory.

## Constraints and review focus

- Do not move source directories. Do not install into live AppData or modify/archive the user's old vault.
- Explicit false integration selections must survive GUI initialization; unspecified values use saved defaults.
- Supplied package and vault must reach the service; non-visible profile fields must not be lost.
- Crash recovery, concurrent user edits, reparse rejection and file modes must remain protected.
- Inventory includes tracked and non-ignored project files, excluding dependencies/build caches; descriptions must explain actual responsibilities.
- Only demonstrably redundant files are removed; historic decision records and recoverable backups are retained.
- GitHub publication uses ordinary pushes, no force pushes and no release tag without a requested release.
- Actual macOS/Linux execution requires remote CI; Windows source checks alone are not platform evidence.

## Task 1: GUI options

Files: src/respectedbrain/cli.py, installation/wizard.py, tests/wizard_options_test.py.

- [x] Add failing CLI dispatch and headless wizard initialization/action tests for vault, package, profile and explicit integration false.
- [x] Pass optional vault/package/profile/desired into wizard main and SetupWizard; overlay explicit values after existing defaults and preserve hidden profile settings. Saved hidden profile is bound to the current selected target even after typing/browsing a different vault; explicit launch overrides remain separate.
- [x] Run new tests and existing wizard/setup tests (33 tests, including 12 new GUI regressions).

## Task 2: Installation throughput

Files: installation/transaction.py, tests/transaction_performance_test.py; evidence in ignored task workspace.

- [x] Profile representative disposable installation and transaction baseline.
- [x] Add a regression exposing redundant durable journal snapshots; verify it fails before changing code (40 vs budget 20 snapshots; nested path 7 vs budget 2).
- [x] Reduce redundant snapshot work without changing schema or dropping synchronization; prove recovery and concurrent-edit behavior with existing fault tests.
- [x] Compare measured timings and run transaction/setup/update/uninstall regressions (42 tests passed). Same 1065-file payload with cProfile enabled: 173.833s to 53.086s; snapshots 2318 to 1202. These are controlled profiled timings, not a promise for live hardware.

## Task 3: Atlas and repository audit

Files: docs/REPOSITORY_MAP.md, tools/repository_map.py, docs/repository_inventory.json, tests/repository_map_test.py, .github/workflows/ci.yml, README.md, docs/REPOSITORY_AUDIT.md.

- [x] Read every tracked file and annotate its role, responsibility and relationships in the inventory.
- [x] Add failing coverage/ghost/duplicate/stale-description tests; implement deterministic generation and --check (11 tests passed).
- [x] Generate tree, architecture boundaries, exhaustive inventory, local artifacts, navigation and maintenance policy (270 final project files).
- [x] Inspect all files for references, dead content and packaging inclusion. Record actionable findings and justified removals; correct import reload test hygiene and inherited-PYTHONPATH wheel isolation. Remove eight unused legacy Claude hook assets and package-data entries; retain historical documents, migration code and backups.
- [x] Update map and add CI/release drift gate. New discovery is automatic; semantic explanations require content review in the same change.

## Task 4: Verification and publication

- [ ] Build and verify Windows native package; run full Python suite, shell and Windows acceptance tests in disposable locations.
- [ ] Fresh independent branch review; address important findings and re-run affected checks.
- [ ] Inspect remote history/auth, stage branch and run all real platform CI checks, then integrate and publish main when green.
- [ ] Record results and limits in audit/plan, regenerate atlas, finish memory handoff. User performs fresh-vault backup/creation later.

## Local evidence before platform staging

Full source suite completed: **650 tests, 868.972s, OK (15 skips)**. Discovery occurred before the last four GUI and two atlas regressions were added; those final files were separately verified in the 33-test GUI/setup suite and 11-test atlas suite. Final source discovery has 656 tests; remote native jobs will discover that final tree. Frozen distribution verification and the Windows host smoke passed (all 16 checks; fresh package install 35.303s, two updates and owned-only uninstall preserve notes and restore test registrations). After the final hook removal and GUI action fix, a fresh Windows build and native acceptance are required and tracked above.

Fresh independent review passed after the action-time vault-profile fix: 32 setup/operations/locking/runtime cases and 38 focused cases (5 host skips); no outstanding introduced findings. Shell hook cases 8/8 and temporary Git upstream scenarios 9/9 passed. Existing hardening limitations are recorded in [the audit](../../REPOSITORY_AUDIT.md); this change does not claim to close them.

## Platform staging follow-up — 2026-10-05

scope: project; confidence: verified; supersedes: []

The historical results above remain dated evidence. Commit 657735c's actual
CI run 37231789231 passed Linux native execution and macOS frozen launcher
checks. Full-suite failures exposed OS temp aliases in fixtures and owned temp
allocations, Windows global Python scripts-directory assumptions, and Inno
compiler discovery. Fixes preserve arbitrary payload/user-path rejection.
macOS smoke now keeps the .app suffix for both package and install destination.

Windows intermittent Dashboard replacement errors were reproduced on Python
3.12/3.13. The prepared output now retries only Windows error codes 5/32, at
most five attempts, aborting on a changed Dashboard and never recalling the
model. Fresh affected-suite verification: 92 tests / 30.739s / OK (7 host
skips). Original eight-thread concurrency case: 100 runs on Python 3.13 /
17.797s / OK. Previous complete local discovery: 662 tests / 791.651s / OK
(15 skips), before the eight latest regressions; it does not cover them.

Root AGENTS.md persists same-task atlas maintenance; the inventory now includes
271 files. CI additionally verifies actual mounted macOS DMG and extracted
Linux makeself payloads. These new release-format checks and the final native
full suites still require a fresh remote run before main integration.

### Native follow-up evidence — 2026-10-05

Commit 869d64f: Windows rebuild and frozen verification passed; all three real
native install/update/uninstall, in-use executable rollback and readonly-app
checks passed (321.464s). Run 37234992142 passed the Linux native/full-suite/
host smoke and verified extracted makeself release archive. macOS full-suite
exposed three additional raw-temp fixture roots. A real Windows junction
reproduced those errors; canonical fixture roots passed all 22 affected cases
(3.014s). A broader alias audit also reproduced setup/operations fixture errors;
the same two fixture-root corrections passed all 125 broader alias cases
(48.703s). No product
path-security policy was relaxed. Main publication remains pending.
