# Cross-Platform Runtime Hardening Design

**Date:** 2026-09-02
**Target:** Respected Brain multi-AI 1.4.0
**Status:** Approved for implementation planning

## Goal

Fix the confirmed Windows Native and Windows–WSL failures in background
summarization, knowledge compilation, hook transcript discovery, scheduled-task
installation, and native setup without changing the existing multi-AI provider
selection and fallback contract.

## Non-goals

- Reordering `PROVIDERS` or changing the meaning of `summary_provider: auto`.
- Falling back after authentication or persistent configuration errors.
- Weakening compile staging, output allowlists, symlink/reparse-point checks, or
  live-vault promotion validation.
- Guessing undocumented stdin support for Cursor Agent.
- Installing into an additional user profile unless the user explicitly names it.
- Replacing working JSON serialization with path-string substitutions.

## Confirmed baseline

- The repository is clean at multi-AI 1.3.0.
- The portable Python suite passes 116 tests; seven native-Windows integration
  tests are skipped outside Windows.
- `runtime_platform.detached_process_options()` already hides detached native
  Windows processes.
- `install_briefing_schedule.py` already decodes UTF-16 and Turkish OEM output.
- `render_integrations.py` serializes Windows paths through `json.dumps`, so
  backslashes are already valid JSON escapes.
- Local Antigravity CLI 1.1.24 documents `--print`, `--input-format text`,
  `--new-project`, `--add-dir`, `--mode accept-edits`,
  `--dangerously-skip-permissions`, and `--sandbox`.
- A WSL-to-`cmd.exe` probe confirms that Windows path values such as
  `C:\\Users\\...` are corrupted when passed through an existing `WSLENV /p`
  entry, while `/mnt/c/Users/...` values are correctly translated to native
  Windows paths.
- A Windows executable started from WSL `/tmp` receives a UNC working directory;
  `cmd.exe` rejects it and falls back to `C:\\Windows`, which loses the intended
  workspace context.

## Provider-selection contract

The candidate builder remains behaviorally unchanged:

1. A configured provider other than `auto` is first.
2. The provider that emitted the hook is next when it is not already first.
3. Remaining providers follow the existing `PROVIDERS` order with duplicates
   removed.
4. Missing executables are skipped.
5. Rate limits, quota/capacity failures, timeouts, transient connection errors,
   and HTTP 5xx signals advance to the next candidate.
6. Authentication and persistent configuration failures stop immediately and
   remain visible.
7. `BEYIN_LLM_COMMAND` remains an explicit stdin-consuming override.

This contract applies to flush, compile, and morning briefing through the
existing `run_model()` API.

## Provider invocation model

`model_runner.py` will represent each provider invocation as structured data:
argv, stdin payload, executable kind, and mode-specific process requirements.
`run_model()` keeps its current public arguments and return tuple.

### Claude

Claude keeps its existing stdin transport and restrictive text/workspace tool
sets. No model or fallback behavior changes.

### Codex

Codex uses `codex exec --ephemeral --sandbox <mode> -` and receives the prompt
through stdin. This is the locally documented Codex CLI contract and removes
the prompt from the process command line.

### Antigravity

Both modes use stdin with `--print --input-format text --output-format text`, a
new isolated project, and slash-command expansion disabled.

- Text mode uses terminal sandboxing and grants no edit mode.
- Workspace mode operates only in the isolated compile stage, adds that stage
  as the workspace, selects `accept-edits`, and auto-approves tool permissions.
  Terminal sandboxing and the compiler's post-run manifest allowlist remain in
  force.

The reported `-p -` workaround is not used because Antigravity 1.1.24 defines
`-p` as the boolean alias for `--print`, not as a prompt-valued option.

### Cursor

Cursor keeps the existing tested argv contract until a supported stdin
interface can be verified against an installed or official CLI contract. This
release does not invent a new Cursor invocation syntax.

## Windows process context

The runtime gains focused helpers for synchronous hidden child processes and
Windows-interoperable temporary storage.

When a selected executable is a Windows binary launched from WSL:

- derive the Windows user root from the vault/module path only when it matches
  `/mnt/<drive>/Users/<user>`;
- set `USERPROFILE`, `LOCALAPPDATA`, and `APPDATA` to their `/mnt/...` forms;
- add or repair their `/p` entries in `WSLENV` without deleting unrelated
  entries;
- preserve existing profile values when they are already valid;
- never log tokens or the full inherited environment.

Flush and compile temporary directories use a Windows-accessible external temp
root when the vault resides under `/mnt/<drive>/Users/<user>`. Compile continues
to execute in its stage; it never falls back to the live vault or `C:\\Windows`.
Portable Linux/macOS and native Windows retain their system temp behavior.

Synchronous native Windows model processes receive `CREATE_NO_WINDOW`.
Detached lifecycle processes keep the current process-group and detach flags.

## Antigravity transcript resolution

An explicit `transcript_path` or `transcriptPath` remains authoritative. When it
is absent and the provider is Antigravity, the bridge may derive a transcript
only when the session identifier contains safe filename characters and no path
separator or traversal component.

The resolver checks, in order:

1. `~/.gemini/antigravity-ide/brain/<session>/.system_generated/logs/transcript.jsonl`
2. `~/.gemini/antigravity-cli/brain/<session>/.system_generated/logs/transcript.jsonl`

It accepts only an existing regular file reached within the corresponding
`brain` root. It performs no recursive home-directory scan. If neither file is
present, normalization leaves the path empty and the existing fail-closed
health behavior remains.

## Summary and compiler output contracts

The flush prompt explicitly requires either `FLUSH_BOS` or the five-section
document beginning directly with `## Bağlam`.

A normalization function may discard non-heading conversational preamble or a
single surrounding Markdown fence before validation. The normalized document
is accepted only if it contains exactly these headings, once, at level two and
in order:

1. `Bağlam`
2. `Önemli Konuşmalar`
3. `Alınan Kararlar`
4. `Öğrenilenler`
5. `Yapılacaklar`

Missing, additional, duplicated, reordered, or wrong-level headings remain a
schema failure. The normalized content—not the raw model response—is appended
to `daily/`.

The compiler prompt states that success means editing the allowed stage files,
not returning conversational prose. Enforcement remains structural: only
validated diffs beneath the existing knowledge allowlist can be promoted.

## Windows scheduled task installation

For Windows task plans, the XML file is created under the explicitly supplied
user home when invoked from WSL. Before passing `/XML` to `schtasks.exe`, a WSL
path is converted with `wslpath -w`. Native Windows paths pass through
unchanged. Query, create, verification, legacy migration, backup, and rollback
ordering remain unchanged.

The existing byte-oriented UTF-16/OEM decoding is retained; Python text-mode
decoding is not introduced at this boundary.

## Native PowerShell probe

`Invoke-ExternalProbe` remains an external-process probe with captured stdout,
stderr, and exit code, but gains a finite timeout. A timed-out child is
terminated, its temporary capture files are cleaned, and the probe returns a
stable nonzero timeout result. Provider, Git, Python, `.cmd`, `.bat`, and `.exe`
probes retain the same caller-visible shape.

Direct `&` invocation is not used because it would remove the temporary-file
symptom without bounding a genuinely hung provider process.

## Multiple Antigravity homes

`install_global.py` gains a repeatable `--antigravity-home <path>` option.

- `--home` continues to own Codex, Cursor, Claude, and the default Antigravity
  profile.
- Each additional Antigravity home receives only Antigravity hooks, rules, and
  skills.
- An already-listed path is de-duplicated.
- Every target must exist and pass the same containment/symlink checks used for
  the primary home.
- Preview lists every managed target.
- Apply uses a separate backup root per home and rolls back that home's partial
  writes on failure.
- Omitting the option preserves the existing single-home behavior.

`install_antigravity_global.py` accepts the same repeatable home concept for its
Antigravity-only compatibility entry point. Documentation shows the common
Windows + Connect-to-WSL pair explicitly.

## Testing strategy

Every production change follows red-green-refactor. Tests assert behavior rather
than source strings wherever the boundary can be executed.

Required regression coverage:

- configured, current-agent, and default candidate order remains unchanged;
- missing, retryable, and non-retryable provider outcomes retain their distinct
  behavior;
- Codex and Antigravity keep large prompts out of argv and deliver them via
  stdin;
- Antigravity text and workspace modes receive different permissions;
- WSL profile environment values translate to valid Windows paths;
- a WSL-hosted vault chooses a Windows-accessible external stage/temp root;
- synchronous Windows children receive the no-window flag;
- safe Antigravity session IDs resolve IDE and CLI transcripts, while traversal
  and missing files fail closed;
- a conversational preamble around a valid summary is normalized, while every
  malformed heading variant is rejected;
- compiler prompts demand stage edits and the existing allowlist still rejects
  forbidden writes and deletions;
- WSL scheduled-task creation passes a Windows XML path and native Windows
  behavior is unchanged;
- native probes return after timeout and preserve normal exit/output behavior;
- primary plus additional Antigravity homes render idempotently, remain
  provider-selective, and roll back safely;
- generated template helpers have no drift;
- the full portable suite, shell tests, and available native PowerShell tests
  pass before release claims.

## Release and compatibility

The fixes target multi-AI 1.4.0. Public function signatures used by flush,
compile, morning briefing, rendering, and updater code remain compatible.
Template copies of managed scripts are regenerated from repository scripts.
Version stamps and updater manifests change only in the later release task, not
as an incidental part of an individual bug fix.
