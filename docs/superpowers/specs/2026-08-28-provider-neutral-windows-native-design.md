# Provider-Neutral Native Windows Design

**Status:** Proposed
**Date:** 2026-08-28
**Scope:** Respot Brain native Windows foundation only

## Goal

Make a Respot Brain vault work on native Windows without WSL while preserving the same
Claude, Codex, Cursor and Antigravity memory behavior already supported on portable POSIX and
Windows+WSL profiles. Native Windows must be a third profile, not a replacement for either
existing path.

This design is the first of three separately delivered projects:

1. provider-neutral native Windows foundation;
2. doctor plus bounded event log;
3. opt-in encrypted backup.

The latter two are intentionally outside this spec and receive their own design and approval
cycles after this foundation ships.

## Reviewed sources

The design adapts behavior rather than merging a fork wholesale:

- `avenoxai/avenoxbeyin@18c83ff`: accepted upstream Windows baseline;
- `morp1e/windows-support@ac207ee`: PowerShell hooks, Windows preflight, portable lock lessons;
- `enesadakli/windows-native@920b597`: native Python lifecycle, reparse-point checks and Windows
  installer tests;
- current Respot `main`: provider bridge, model fallback, WSL path conversion and generated
  four-agent adapters.

Source decisions and deferred features remain recorded in `docs/UPSTREAM-SYNC.md`.

## Approaches considered

### Chosen: one Python lifecycle core with thin launchers

Move lifecycle behavior currently implemented in four Bash hooks into one provider-neutral Python
module. POSIX shell hooks remain as compatibility launchers, while native Windows and existing
provider bridges call the same Python core directly.

Benefits:

- one implementation of session context, counters, reflection state and detached flush;
- no behavioral drift among PowerShell, Bash and Python copies;
- all four agents use the same runtime on every platform;
- upstream Windows locking and process lessons can be adopted without Claude-only assumptions.

Cost: this changes a security-sensitive lifecycle boundary and therefore requires parity tests
against every current hook behavior before the Bash implementation can be reduced to wrappers.

### Rejected: keep Bash and add a Windows-only Python hook

This is close to the Enes fork and would be quicker initially, but it creates two complete state
machines. Every future fix would have to land twice and parity could only be inferred from tests.
Respot's purpose is one memory system across agents, so duplicate lifecycle engines are the wrong
long-term boundary.

### Rejected: translate every hook to PowerShell

This is close to the Morp1e fork. It adds a third language implementation, requires PowerShell
process wrappers for non-Claude agents, and does not solve provider neutrality. PowerShell remains
appropriate for Windows preflight and installation, not for the canonical memory behavior.

## Architecture

### Canonical runtime files

The installed vault gains these canonical files:

```text
.beyin/
├── hooks/
│   ├── bridge.py             provider payload normalization and provider output shape
│   └── lifecycle.py          shared start/prompt/end/precompact behavior
├── runtime_platform.py       portable locks, detached process flags, path/reparse checks
├── model_runner.py           existing provider selection and quota fallback
└── config.json               provider choice plus installed platform profile
```

`lifecycle.py` owns:

- SessionStart state initialization, stale-state cleanup and the 16,000-character context budget;
- UserPromptSubmit atomic per-session counting and every-15-message reminder;
- SessionEnd and PreCompact managed hook-input files, detached flush launch, reflection markers and
  session-scoped cleanup;
- completed-day compile catch-up after context output;
- recursion guard behavior.

`bridge.py` continues to own only provider-specific input and output translation. It must not
reimplement lifecycle state. The runtime accepts a normalized dictionary plus `event`, `provider`
and `vault_root`, and returns an optional context string.

### Compatibility launchers

The existing `.claude/hooks/*.sh` files remain at their current paths so existing POSIX settings,
upgrade manifests and user trust records do not break. Each becomes a small wrapper that:

1. exits immediately when `BEYIN_INVOKED_BY` is set;
2. resolves `CLAUDE_PROJECT_DIR`;
3. executes `python3 .beyin/hooks/bridge.py --provider claude --event <event>`;
4. passes stdin and stdout through unchanged.

`bridge.py` calls `lifecycle.handle(...)` and emits the Claude hook response shape. No lifecycle
policy remains in shell after parity tests prove the Python implementation.

### Portable machine primitives

`runtime_platform.py` provides narrowly scoped functions:

- `exclusive_lock(handle, blocking, timeout)` using `fcntl.flock` on POSIX and
  `msvcrt.locking` on Windows;
- `detached_process_options()` using `start_new_session=True` on POSIX and
  `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW` where available on Windows;
- atomic exclusive-file claim creation that treats Windows `PermissionError` during an
  `O_CREAT | O_EXCL` race as contention rather than a lost hook event;
- vault containment checks that reject symlinks on POSIX and reparse-point/junction escapes on
  Windows.

`flush.py`, `compile.py` and `lifecycle.py` consume this module. No module imports `fcntl`
unconditionally after migration.

## Platform profiles

All public installers and renderers accept exactly these profiles:

| Profile | Hook runtime | Vault path model | Status after this project |
| --- | --- | --- | --- |
| `portable` | `python3` plus thin shell launchers | POSIX | Existing behavior preserved |
| `windows-wsl` | `wsl.exe --cd <vault> python3` | `/mnt/<drive>/...` with Windows translation | Existing behavior preserved |
| `windows-native` | `py.exe -3` direct Python | `C:\...` | New and CI-verified |

`auto` is allowed only at user-facing migration entry points. Generated adapter files always store
an explicit profile so later rendering is deterministic.

`.beyin/config.json` gains:

```json
{
  "summary_provider": "auto",
  "platform": "windows-native",
  "python_command": ["py.exe", "-3"]
}
```

Existing config values are preserved. Missing `platform` and `python_command` are inferred once by
the updater and then written explicitly. Arbitrary shell strings are not accepted; the Python
command is an argv array.

## Generated provider adapters

`scripts/render_integrations.py` gains `windows-native` and uses one command builder for project
and global adapters:

- Claude: `.claude/settings.json` invokes `py.exe -3 .beyin/hooks/bridge.py --provider claude`;
- Codex: `.codex/hooks.json` uses native `commandWindows` without `wsl.exe`;
- Cursor: `.cursor/hooks.json` uses the same native bridge command;
- Antigravity: `.agents/hooks.json` uses the same native bridge command.

Provider event coverage remains unchanged. Antigravity's repeated `PreInvocation` guard and Cursor's
provider-specific output shapes stay in `bridge.py`.

Commands are built from argv components and quoted with Windows command-line rules. User input,
vault names and transcript content never become executable fragments. Installed native adapters
use the absolute Windows vault path so their behavior does not depend on an IDE's current working
directory; repository template fixtures may remain relative until installation renders them.

## Windows installation and global connection

### Fresh install

`scripts/install-windows.ps1` is a bootstrap and preflight layer. It validates by execution rather
than command presence:

- a real Python 3 interpreter, rejecting the Microsoft Store alias stub;
- Git;
- at least one user-selected local AI CLI from Claude, Codex, Cursor or Antigravity;
- a writable parent for the requested vault path.

It does not require Claude when another supported provider is selected. It copies the template,
fills placeholders, writes explicit `windows-native` config, renders adapters, initializes Git and
runs the native smoke checks. It refuses an existing non-empty target and never installs software
without user approval.

PowerShell 7 is preferred but not a runtime dependency: hooks call Python directly. The preflight
and bootstrap remain compatible with Windows PowerShell 5.1 so a missing `pwsh` cannot hide the
actual dependency report.

### Existing Respot vault

`scripts/update_respot.py` becomes the supported update transaction for an already stamped Respot
vault on all profiles. It:

1. previews managed files without mutation;
2. validates the existing core and multi-AI stamps;
3. takes a timestamped backup outside generated adapter paths;
4. updates runtime and canonical helper files;
5. renders the explicit installed profile;
6. runs syntax, adapter-drift and required-file gates;
7. writes `.beyin-multi-version` last.

Native Windows foundation advances the multi-AI stamp from `1.0.0` to `1.1.0`. A failed update
leaves the old stamp and backup intact. `enable_multiai.py` remains the v2-to-Respot bootstrap and
repair tool; it is not the routine updater.

### Existing v1 vault on native Windows

Native conversion of an unstamped v1 vault is not part of this first foundation. The documented
safe route remains the verified WSL transaction. The Windows updater must refuse a v1 target rather
than partially stamping it. A native v1 migration can be designed after fresh install and existing
Respot update are proven on Windows CI and a real Windows machine.

### Global connections

`scripts/install_global.py` accepts `windows-native`, Windows-native home/vault paths and native
bridge commands. It preserves unrelated user rules and hooks exactly as the current portable/WSL
installer does. Provider selection remains independent; `--providers codex` does not install or
require Claude artifacts beyond the shared vault runtime.

## Data flow

```text
native provider event
        ↓
generated provider adapter (`py.exe -3 ...bridge.py`)
        ↓
bridge.normalize(provider payload)
        ↓
lifecycle.handle(event, normalized payload)
        ↓
shared state / detached flush.py
        ↓
model_runner.py provider selection and fallback
        ↓
daily/ and knowledge/
```

No GUI is opened. Background summaries use whichever authenticated local provider the existing
Respot selection/fallback policy chooses.

## Security and failure behavior

- Hook boundaries remain fail-open for the coding agent: malformed input records health state and
  returns a valid empty provider response instead of blocking the IDE.
- Runtime writes are restricted to known state, daily and knowledge paths.
- Transcript and daily text remain untrusted data; model output schemas and compile staging
  allow-lists remain mandatory.
- Native path containment rejects junction/reparse escapes, not only symbolic links.
- Secrets, provider tokens and local settings are never copied into backups or Git staging.
- The updater and installer use explicit file allow-lists and atomic replacement.
- Provider quota fallback behavior remains unchanged; native Windows support cannot silently
  switch the configured summary provider or authorize paid API use.
- When Python or every selected CLI is unavailable, the doctor/health state reports the failure;
  hooks do not fabricate a successful daily write.

## Testing and acceptance

### Cross-platform parity

The existing POSIX suites remain mandatory. New lifecycle tests execute the Python core directly
and the shell wrappers end-to-end. For each event they assert the same observable state and output:

- exact SessionStart sections and hard character limits;
- stale-state cleanup;
- serial and concurrent prompt counting;
- per-session end/precompact isolation;
- recursion guard;
- detached flush arguments and managed input cleanup;
- completed-day compile catch-up.

### Windows CI

A `windows-latest` GitHub Actions job runs with Python 3.13 and PowerShell. Agent CLIs are complete
test stubs, so CI consumes no quota. It must cover:

- native lock contention and 24-process counter increments;
- detached child behavior;
- fresh installer preflight, refusal and idempotent generated output;
- four provider adapter command shapes with no `wsl.exe` or Bash dependency;
- start/prompt/end/precompact through native bridge commands;
- Antigravity transcript normalization and provider-first model fallback;
- config/stamp update from `1.0.0` to `1.1.0` with rollback on a forced gate failure;
- junction/reparse containment rejection where runner privileges permit it.

### Release gates

The project is complete only when:

1. all existing Linux/WSL tests pass unchanged or with explicitly reviewed wrapper expectations;
2. the full Windows CI job passes;
3. `render_integrations.py --check` is clean for all three profiles;
4. a real Windows smoke test proves one provider start and end event writes a daily entry;
5. switching to a second provider reads that entry at SessionStart;
6. no native generated hook command contains `wsl.exe`, `bash` or a POSIX vault path;
7. docs state native v1 migration remains unsupported instead of implying otherwise.

## Documentation changes

README, SETUP, MULTI_AI and SPEC gain a three-profile matrix. `SETUP-WINDOWS.md` becomes the native
runbook and names all four providers. WSL instructions remain available and are not relabeled as
legacy. `docs/UPSTREAM-SYNC.md` records the exact imported Windows behaviors and the Respot-specific
changes made to preserve provider neutrality.

## Explicit non-goals

- Restic, DPAPI, Task Scheduler and disaster recovery;
- immutable bridge event history or expanded doctor checks;
- native migration of an unstamped v1 Windows vault;
- installing or authenticating AI CLIs without user approval;
- replacing Obsidian or storing raw agent chat history in the vault;
- removing the verified Windows+WSL path.
