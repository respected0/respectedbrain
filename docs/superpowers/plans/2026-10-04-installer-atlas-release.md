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

- [x] Build and verify Windows native package; run full Python suite, shell and Windows acceptance tests in disposable locations. Final product build/frozen verification and native 3/3 passed; earlier shell 8/8, upstream 9/9 and Windows launcher/scheduler acceptance passed. Current full local suite: 670 / 460.647s / OK (15 host skips).
- [x] Fresh independent branch review; address important findings and re-run affected checks. 2026-10-05 review found no important new issue; 64 independent scoped cases and 12 diagnostics cases passed. Final test-fixture roots additionally undergo complete source alias verification.
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

### Complete alias investigation — 2026-10-05

Run 37235731550: Linux native and release archive verification passed. Windows
and macOS full-suite failures were fixture-root aliases. GitHub retained only
ten error annotations per step, hiding additional failures. A whole-source
real-junction reproduction (excluding only the three expensive native install
cases in the throwaway harness) ran 668 tests and identified exactly five
remaining fixture modules: POSIX install, old update, briefing fault injection,
vault registry, wizard options. All 69 affected cases passed after only fresh
fixture-root .resolve corrections (3 existing host skips).

Public-ID diagnostics now aggregate one safe annotation; real twelve-failure
fixture first failed (12 annotations) and then passed (one annotation, all IDs,
no exception/subtest payload). Independent diagnostic review passed 12/12.
Normal local full suite on 598fede completed 670 / 460.647s / OK (15 skips),
before the extra diagnostic case. Final actual platform proof remains pending;
no failing test was deleted or permanently skipped to obtain these results.

Full-source real-junction alias GREEN: 668 tests, zero failures/errors, 15
existing host skips. RED was 38 failures + 2 errors; the same harness excluded
only FoundationNativeInstallTest, whose three real cases separately passed.
Final discovery includes 671 tests. No production changes in this follow-up.

### Python 3.10 compatibility investigation — 2026-10-05

Run 37236806337 passed all three native build/full-suite/physical smoke and
release-format jobs, plus all three Python 3.13 source jobs. Its three Python
3.10 source jobs failed. A checksum-verified isolated CPython 3.10.22 reproduced
136 discovery errors and two failures: ResourceCatalog imported the Python
3.11+ importlib.resources.abc module unconditionally. The type now falls back
to Python 3.10's importlib.abc.Traversable, preserving runtime introspection.
All four existing resource/wheel-isolation tests passed on actual Python 3.10;
17 resource/diagnostics tests passed on Python 3.12 (5.849s).

Python 3.10's unittest headers omit the final method inside parentheses.
Diagnostics normalize that restricted public class identifier to the same
canonical test ID while excluding exception/subtest data. A new RED/GREEN
case covers this older format. Independent review found no new issue; all
13 diagnostics tests passed. Final discovery now includes 672 tests.
The isolated runtime is ignored task evidence; no global Python, provider
settings, live program or vault was changed. Fresh full-suite/platform results
are required before main publication.

A second actual 3.10 parser failure was isolated in Codex notify's WSL path
conversion: a backslash inside an f-string expression needs Python 3.12+.
The identical calculation now occurs in a separate tail variable. Existing
turn-log/chain tests passed 10/10 on Python 3.10 and 10/10 on Python 3.12;
actual Python 3.10 parsed all 155 source/test/tool Python files successfully.
The first broader run after the resource fix captured this syntax error and
an uninstalled editable entrypoint in the isolated runtime. After installing
only into that disposable runtime, a fresh full run covers the final code.

Fresh isolated CPython 3.10.22 source GREEN: 669 tests, zero failures/errors,
15 existing host skips. Only the three FoundationNativeInstallTest cases are
excluded by the throwaway harness, not permanently skipped. Native execution
is separately required by the fresh CI. Final Windows distribution and Inno
installer rebuilt; frozen version/registry/maps/search/hook/MCP passed. All
1057 copied distribution files match SHA256 in primary dist; previous build
is preserved in ignored evidence. No introduced finding in independent review
of either compatibility change or diagnostics normalization.

### Earlier compatibility and reduced CI repetition — 2026-10-05

Run 37239730909 passed all three native build/frozen/physical smoke/acceptance/
release-format jobs and the Linux/macOS 3.13 source jobs. Windows native full
suite took 7.3 minutes; the previous run took 9.4 minutes plus 4.7 minutes for
physical smoke. Python 3.10 POSIX jobs exposed a test-only global os.name mock
that changes Python 3.10 Path construction, and a macOS wheel-isolation error
whose substage is not yet established. The OS fake now patches only the product
module adapter; package diagnostics expose only one of six fixed stage labels.

The user asked about waiting cost and runtime. CI now runs 37 minimum-version
import/wheel/host-adapter tests on all three hosts before native work. The
duplicated native-stage 3.13 full suite is removed; all six source host/version
full suites still consume the verified native artifacts and include native
acceptance cases. Native launcher/smoke/Inno/scheduler/real-format and shell
gates remain. Actual 3.10 early scope: 37 / 6.737s / OK (one host skip);
3.12 changed fixtures/release contract: 19 / 4.724s / OK (one host skip).
Independent narrow review found no introduced important issue. No product
change or rebuild is needed for this follow-up. Discovery now includes 673.
macOS's failed substage must be diagnosed and all final gates green before
main publication; a local host pass cannot stand in for the other platforms.
