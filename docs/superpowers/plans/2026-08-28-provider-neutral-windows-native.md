# Provider-Neutral Native Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native Windows profile that runs the same Respot lifecycle and provider fallback for Claude, Codex, Cursor and Antigravity without requiring WSL.

**Architecture:** Move lifecycle behavior from four Bash hooks into one Python module called by the existing provider bridge; retain Bash only as thin POSIX compatibility launchers. Add portable lock/process primitives, deterministic three-profile rendering, a stamped Respot updater, native global/fresh installers and Windows CI while preserving the current portable and Windows+WSL contracts.

**Tech Stack:** Python 3.13 standard library, Bash compatibility wrappers, PowerShell 5.1-compatible bootstrap, JSON hook manifests, `unittest`, shell integration tests and GitHub Actions Windows runners.

**Spec:** `docs/superpowers/specs/2026-08-28-provider-neutral-windows-native-design.md`

## Global Constraints

- Supported profiles are exactly `portable`, `windows-wsl` and `windows-native`; `auto` is accepted only by migration/update entry points.
- Native Windows hooks use an argv command equivalent to `py.exe -3` and never require `wsl.exe`, Bash or a POSIX vault path.
- Claude, Codex, Cursor and Antigravity share one lifecycle implementation and the existing `model_runner.py` fallback policy.
- Existing portable and Windows+WSL behavior, adapter formats, user rules, skills and vault memory are preserved.
- Native Windows foundation advances `.beyin-multi-version` from `1.0.0` to `1.1.0`; the stamp is written only after verification gates pass.
- Native migration of an unstamped v1 Windows vault, doctor/event-log expansion and Restic backup are outside this plan.
- No dependency installer, provider authentication or paid API authorization runs without explicit user approval.
- The user's single-branch preference is preserved; implementation commits land on `main` without persistent feature or backup branches.

---

### Task 1: Portable Runtime Primitives

**Files:**
- Create: `template/.beyin/runtime_platform.py`
- Create: `tests/runtime_platform_test.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `exclusive_lock(handle: IO[str], *, blocking: bool, timeout: float = 300.0) -> ContextManager[bool]`
- Produces: `detached_process_options() -> dict[str, int | bool]`
- Produces: `create_exclusive_claim(path: Path, mode: int = 0o600) -> bool`
- Produces: `path_within_vault(path: Path, vault_root: Path) -> bool`
- Consumes: Python `fcntl` on POSIX and `msvcrt` only on Windows.

- [ ] **Step 1: Write failing primitive behavior tests**

```python
class RuntimePlatformTest(unittest.TestCase):
    def test_nonblocking_lock_reports_contention(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "lock"
            with path.open("a+", encoding="utf-8") as first, path.open("a+", encoding="utf-8") as second:
                with RUNTIME.exclusive_lock(first, blocking=True) as held:
                    self.assertTrue(held)
                    with RUNTIME.exclusive_lock(second, blocking=False) as second_held:
                        self.assertFalse(second_held)

    def test_exclusive_claim_has_single_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            claim = Path(temporary) / "claim"
            self.assertTrue(RUNTIME.create_exclusive_claim(claim))
            self.assertFalse(RUNTIME.create_exclusive_claim(claim))
            self.assertEqual(stat.S_IMODE(claim.stat().st_mode) & 0o077, 0)

    def test_detached_options_match_host(self):
        options = RUNTIME.detached_process_options()
        if os.name == "nt":
            self.assertIn("creationflags", options)
            self.assertNotIn("start_new_session", options)
        else:
            self.assertEqual(options, {"start_new_session": True})
```

- [ ] **Step 2: Run the new suite and verify RED**

Run: `python3 -m unittest -v tests.runtime_platform_test`

Expected: import/file failure because `template/.beyin/runtime_platform.py` does not exist.

- [ ] **Step 3: Implement the narrow cross-platform API**

```python
@contextlib.contextmanager
def exclusive_lock(handle, *, blocking, timeout=300.0):
    if os.name == "nt":
        held = _acquire_windows(handle, blocking=blocking, timeout=timeout)
    else:
        held = _acquire_posix(handle, blocking=blocking)
    try:
        yield held
    finally:
        if held:
            _release(handle)

def detached_process_options():
    if os.name != "nt":
        return {"start_new_session": True}
    flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    flags |= int(getattr(subprocess, "DETACHED_PROCESS", 0x00000008))
    flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"creationflags": flags}

def create_exclusive_claim(path, mode=0o600):
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    except FileExistsError:
        return False
    except PermissionError:
        if os.name == "nt" and path.exists():
            return False
        raise
    os.close(descriptor)
    return True
```

Implement `path_within_vault` with resolved-path containment, symlink rejection and a Windows
reparse-point check using `os.lstat` file attributes when `os.name == "nt"`.

- [ ] **Step 4: Verify GREEN on the host and syntax on both branches**

Run: `python3 -m unittest -v tests.runtime_platform_test && python3 -m py_compile template/.beyin/runtime_platform.py`

Expected: all host-relevant tests pass; Windows-only tests are decorated with
`@unittest.skipUnless(os.name == "nt", "Windows only")` rather than mocked.

- [ ] **Step 5: Commit**

```bash
git add template/.beyin/runtime_platform.py tests/runtime_platform_test.py .gitignore
git commit -m "Add portable Respot runtime primitives"
```

---

### Task 2: Shared Python Lifecycle Core

**Files:**
- Create: `template/.beyin/hooks/lifecycle.py`
- Create: `tests/lifecycle_test.py`
- Reference: `template/.claude/hooks/lib.sh`
- Reference: `template/.claude/hooks/session-start.sh`
- Reference: `template/.claude/hooks/prompt-counter.sh`
- Reference: `template/.claude/hooks/session-end.sh`
- Reference: `template/.claude/hooks/pre-compact.sh`

**Interfaces:**
- Consumes: `runtime_platform.exclusive_lock`, `runtime_platform.detached_process_options`
- Produces: `handle(event: str, payload: dict[str, Any], vault_root: Path, provider: str, now: datetime | None = None) -> str`
- Produces: `main(argv: Sequence[str] | None = None) -> int` for direct diagnostic execution.
- State contract: existing filenames under `.claude/scripts/.state` remain byte-compatible.

- [ ] **Step 1: Write SessionStart parity tests**

Create a temp vault fixture with Last-Session, Threads, Kurallar, Journal, knowledge index and daily
files. Assert literal section order and limits:

```python
context = LIFECYCLE.handle("start", {"session_id": "s1"}, vault, "codex", fixed_now)
self.assertEqual(
    [line for line in context.splitlines() if line.startswith("[") and line.endswith("]")],
    [
        "[Hafıza: Son Oturum]", "[Hafıza: Aktif Konular]", "[Hafıza: Kurallar]",
        "[Hafıza: Son Journal]", "[Bilgi Tabanı: İndeks]", "[Bugünün Logu]",
    ],
)
self.assertLessEqual(len(context), 16_000)
self.assertEqual((state / f"prompt_count.{session_key('s1')}").read_text().strip(), "0")
```

- [ ] **Step 2: Write prompt/end/precompact RED tests**

Cover these real effects without mocks:

```python
for _ in range(14):
    self.assertEqual(LIFECYCLE.handle("prompt", payload, vault, "antigravity"), "")
self.assertIn("15. mesaj", LIFECYCLE.handle("prompt", payload, vault, "antigravity"))

LIFECYCLE.handle("end", {"session_id": "ended", "transcript_path": str(transcript)}, vault, "codex")
self.assertTrue((state / f"needs_reflection.{session_key('ended')}").exists())
self.assertFalse((state / f"prompt_count.{session_key('ended')}").exists())
self.assertTrue((state / f"prompt_count.{session_key('live')}").exists())
```

Use an executable temp `flush.py` recorder so detached arguments and managed hook-input cleanup are
observed through files, not a subprocess mock.

- [ ] **Step 3: Run lifecycle tests and verify RED**

Run: `python3 -m unittest -v tests.lifecycle_test`

Expected: import/file failure because lifecycle does not exist.

- [ ] **Step 4: Port lifecycle behavior with exact state compatibility**

Implement these focused functions inside `lifecycle.py`:

```python
def session_key(session_id: str) -> str: ...
def start_context(vault_root: Path, state_dir: Path, session_id: str, now: datetime) -> str: ...
def count_prompt(state_dir: Path, session_id: str) -> str: ...
def finish_session(vault_root: Path, state_dir: Path, payload: dict[str, Any], reason: str, now: datetime) -> str: ...
def handle(event: str, payload: dict[str, Any], vault_root: Path, provider: str, now=None) -> str: ...
```

Port the current hard limits and ordering literally from the shell tests. Use atomic temp-file
replacement for state writes, `exclusive_lock` for counters, `sys.executable` for detached Python
children and `BEYIN_PROVIDER=<provider>` in the child environment. Invalid payloads record
`health.json` and return an empty string.

- [ ] **Step 5: Verify lifecycle GREEN and mutation-sensitive boundaries**

Run: `python3 -m unittest -v tests.lifecycle_test`

Expected: tests pass, including concurrent prompt count exactly equal to the number of workers,
other-session state preserved, and catch-up launched after context construction.

- [ ] **Step 6: Commit**

```bash
git add template/.beyin/hooks/lifecycle.py tests/lifecycle_test.py
git commit -m "Add shared provider-neutral lifecycle core"
```

---

### Task 3: Bridge Integration and Thin POSIX Launchers

**Files:**
- Modify: `template/.beyin/hooks/bridge.py:16-171`
- Modify: `template/.claude/hooks/session-start.sh`
- Modify: `template/.claude/hooks/prompt-counter.sh`
- Modify: `template/.claude/hooks/session-end.sh`
- Modify: `template/.claude/hooks/pre-compact.sh`
- Modify: `tests/multiai_test.py:51-75`
- Modify: `tests/hooks_test.sh`

**Interfaces:**
- Consumes: `lifecycle.handle(...) -> str`
- Preserves: `bridge.normalize`, `bridge.output`, Antigravity first-invocation guard and global
  inside-vault deduplication.
- Produces: all four shell hooks as fixed-argument bridge launchers.

- [ ] **Step 1: Write bridge-without-shell RED tests**

```python
with mock.patch.object(bridge.LIFECYCLE, "handle", return_value="ortak bağlam") as handle:
    result = bridge.dispatch("codex", "start", {"session_id": "x"})
self.assertEqual(result, "ortak bağlam")
handle.assert_called_once()
self.assertNotIn("EVENT_SCRIPT", vars(bridge))
```

Add an end-to-end wrapper test using a temp copied vault and real Python lifecycle. Delete the
legacy `.claude/hooks/lib.sh` helper after setup while keeping the four launcher files; wrapper
execution must still succeed, proving that lifecycle behavior no longer depends on the old shell
implementation.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3 -m unittest -v tests.multiai_test.MultiAITest.test_bridge_dispatches_to_shared_lifecycle && bash tests/hooks_test.sh`

Expected: missing `dispatch`/`LIFECYCLE` and old shell-content expectations fail.

- [ ] **Step 3: Replace bridge subprocess delegation with direct lifecycle dispatch**

```python
def dispatch(provider: str, event: str, payload: dict[str, Any]) -> str:
    if os.environ.get("BEYIN_INVOKED_BY"):
        return ""
    normalized = normalize(provider, payload)
    return LIFECYCLE.handle(event, normalized, ROOT, provider)
```

Keep provider output formatting unchanged. Replace each shell hook with a recursion guard, root
resolution and `exec python3 "$CLAUDE_PROJECT_DIR/.beyin/hooks/bridge.py" --provider claude
--event <event>`.

- [ ] **Step 4: Verify provider and POSIX parity GREEN**

Run: `python3 -m unittest -v tests.multiai_test tests.lifecycle_test && bash tests/hooks_test.sh`

Expected: bridge tests and the complete existing shell behavior suite pass.

- [ ] **Step 5: Commit**

```bash
git add template/.beyin/hooks/bridge.py template/.claude/hooks tests/multiai_test.py tests/hooks_test.sh
git commit -m "Route every agent through the shared lifecycle"
```

---

### Task 4: Make Flush and Compile Native-Portable

**Files:**
- Modify: `template/.claude/scripts/flush.py:6-20,428-514,559-675`
- Modify: `template/.claude/scripts/compile.py:6-25,788-855`
- Modify: `tests/scripts_test.py`
- Modify: `tests/runtime_platform_test.py`

**Interfaces:**
- Consumes: `runtime_platform.exclusive_lock`, `create_exclusive_claim`,
  `detached_process_options`, `path_within_vault`.
- Preserves: all flush schemas, Antigravity transcript extraction, compile staging allow-list,
  claim release and completed-day catch-up.

- [ ] **Step 1: Write tests that fail when `fcntl` is unavailable**

Run both scripts in a subprocess whose import hook rejects `fcntl`, but pre-load a fake
`runtime_platform` module that exposes the consumed portable API. Assert module import reaches
argument handling rather than crashing at import. This isolates the property under test: neither
engine may import POSIX locking directly. On Windows CI run the real runtime module without an
import hook.

```python
result = subprocess.run(
    [sys.executable, "-c", IMPORT_WITHOUT_FCNTL, str(copied_flush)],
    cwd=vault, text=True, capture_output=True, check=False,
)
self.assertNotIn("No module named 'fcntl'", result.stderr)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.scripts_test.ScriptsTest.test_engine_imports_without_unconditional_fcntl`

Expected: current unconditional `import fcntl` fails.

- [ ] **Step 3: Replace OS-specific operations**

Insert the vault `.beyin` directory into `sys.path`, import `runtime_platform`, then:

```python
with runtime_platform.exclusive_lock(lock_file, blocking=True) as held:
    if not held:
        return 0

if not runtime_platform.create_exclusive_claim(trigger):
    return False

launcher(compile_argv, ..., **runtime_platform.detached_process_options())
```

Compile uses `blocking=False`; a false result returns cleanly and releases the trigger claim.
Replace containment checks with `path_within_vault` while retaining the existing staging
allow-list and special-file checks.

- [ ] **Step 4: Run engine and security suites GREEN**

Run: `python3 -m unittest -v tests.scripts_test tests.runtime_platform_test`

Expected: all tests pass and the current hostile-input, symlink and claim regressions remain green.

- [ ] **Step 5: Commit**

```bash
git add template/.claude/scripts/flush.py template/.claude/scripts/compile.py tests/scripts_test.py tests/runtime_platform_test.py
git commit -m "Make the memory engine native-platform safe"
```

---

### Task 5: Deterministic Three-Profile Rendering

**Files:**
- Modify: `template/.beyin/config.json`
- Modify: `scripts/render_integrations.py`
- Modify: `template/.claude/settings.json`
- Modify: `tests/multiai_test.py`
- Create: `tests/profile_render_test.py`

**Interfaces:**
- Produces: `Profile(name: Literal["portable", "windows-wsl", "windows-native"], python_command: tuple[str, ...])`
- Produces: `bridge_argv(profile: Profile, vault: Path, provider: str, event: str, global_hook: bool = False) -> list[str]`
- Produces: rendered Claude, Codex, Cursor and Antigravity adapter JSON for an explicit profile.

- [ ] **Step 1: Write literal command-shape tests for all profiles**

```python
self.assertEqual(
    render.bridge_argv(Profile("windows-native", ("py.exe", "-3")), PureWindowsPath(r"C:\Users\Ada\Ada Brain"), "codex", "start"),
    ["py.exe", "-3", r"C:\Users\Ada\Ada Brain\.beyin\hooks\bridge.py", "--provider", "codex", "--event", "start"],
)
```

Render each profile into a temp vault. Assert native JSON contains all four providers and contains
none of `wsl.exe`, `/mnt/`, `.sh` or `bash`. Assert WSL output still contains `wsl.exe --cd` and
portable output still uses `python3`.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.profile_render_test`

Expected: `windows-native` is rejected and `Profile`/`bridge_argv` do not exist.

- [ ] **Step 3: Refactor renderer around explicit profile data**

Remove the global `WINDOWS_WSL` boolean. Load `platform` and `python_command` from explicit CLI
arguments/config, serialize Windows command strings using `subprocess.list2cmdline`, and render
`.claude/settings.json` as part of the managed adapter set.

Default template config becomes:

```json
{
  "summary_provider": "auto",
  "platform": "portable",
  "python_command": ["python3"]
}
```

- [ ] **Step 4: Render committed portable artifacts and verify all profiles**

Run:

```bash
python3 scripts/render_integrations.py --platform portable
python3 scripts/render_integrations.py --platform portable --check
python3 -m unittest -v tests.profile_render_test tests.multiai_test
```

Expected: committed template artifacts have no drift and all three temp render profiles pass.

- [ ] **Step 5: Commit**

```bash
git add template/.beyin/config.json template/.claude/settings.json template/.codex template/.cursor template/.agents scripts/render_integrations.py tests/profile_render_test.py tests/multiai_test.py
git commit -m "Render native Windows adapters from one profile model"
```

---

### Task 6: Transactional Respot Updater and Version 1.1

**Files:**
- Create: `scripts/update_respot.py`
- Create: `tests/update_respot_test.py`
- Modify: `scripts/enable_multiai.py`
- Modify: `scripts/upgrade.sh`
- Modify: `tests/upgrade_transaction_test.sh`
- Modify: `SETUP.md`

**Interfaces:**
- Produces CLI: `python scripts/update_respot.py <vault> [--platform auto|portable|windows-wsl|windows-native] [--apply]`
- Consumes stamped Respot core `2.0.0` and multi-AI `1.0.0` or `1.1.0`.
- Produces multi-AI stamp `1.1.0` only after all gates pass.

- [ ] **Step 1: Write updater transaction RED tests**

Create temp `1.0.0` vault fixtures and assert:

```python
before = tree_digest(vault)
preview = run_update(vault)
self.assertEqual(preview.returncode, 0)
self.assertEqual(tree_digest(vault), before)

failed = run_update(vault, "--apply", env={"RESPOT_TEST_FAIL_GATE": "render"})
self.assertNotEqual(failed.returncode, 0)
self.assertEqual((vault / ".beyin-multi-version").read_text().strip(), "1.0.0")

applied = run_update(vault, "--apply")
self.assertEqual(applied.returncode, 0)
self.assertEqual((vault / ".beyin-multi-version").read_text().strip(), "1.1.0")
```

Also assert instructions, selected `summary_provider`, memory notes and unrelated files remain
byte-identical; managed prior files exist in the timestamped backup.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.update_respot_test`

Expected: updater script does not exist.

- [ ] **Step 3: Implement preview/apply/gate/stamp transaction**

Use fixed managed-file tuples shared with `enable_multiai.py`, atomic writes and
`render_integrations.py --check`. Reject missing/unknown core stamps and unstamped v1 targets.
Infer `windows-wsl` only from WSL environment plus `/mnt/<drive>`; infer `windows-native` only when
`os.name == "nt"`; otherwise use portable.

- [ ] **Step 4: Advance bootstrap and upgrade targets to 1.1.0**

Set `MULTI_VERSION`/`BEYIN_MULTI_VERSION` to `1.1.0`, include lifecycle/runtime-platform files in
copy and verification allow-lists, and change transaction expectations from `1.0.0` to `1.1.0`.
Do not treat an existing `1.0.0` stamp as an error in `update_respot.py`.

- [ ] **Step 5: Verify updater and v1 upgrade GREEN**

Run:

```bash
python3 -m unittest -v tests.update_respot_test
bash tests/upgrade_transaction_test.sh
python3 -m unittest -v tests.multiai_test
```

Expected: rollback leaves `1.0.0`; successful update and fresh v1 upgrade produce `1.1.0`.

- [ ] **Step 6: Commit**

```bash
git add scripts/update_respot.py scripts/enable_multiai.py scripts/upgrade.sh tests/update_respot_test.py tests/upgrade_transaction_test.sh SETUP.md
git commit -m "Add transactional Respot 1.1 updater"
```

---

### Task 7: Native Global Connections

**Files:**
- Modify: `scripts/install_global.py`
- Modify: `tests/multiai_test.py`
- Modify: `MULTI_AI.md`

**Interfaces:**
- Changes: `build(vault: Path, home: Path, providers: tuple[str, ...], platform: str) -> tuple[list[tuple[Path, str]], list[Path]]`
- Changes: `bridge_command(vault, provider, event, platform) -> str`
- Preserves: managed markers, unrelated hook/rule content and provider-selective installation.

- [ ] **Step 1: Write native global command and idempotency RED tests**

Build a temp user profile with existing Codex/Cursor rules. Render `windows-native` and assert all
managed commands contain `py.exe -3`, an absolute `C:\...\bridge.py` path and no WSL/Bash token.
Run apply twice and compare all managed bytes outside backup directories.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest -v tests.multiai_test.MultiAITest.test_native_windows_global_installer_is_provider_neutral`

Expected: platform argument is rejected or WSL commands are emitted.

- [ ] **Step 3: Replace the boolean Windows flag with the profile string**

Use the renderer's command builder. Add CLI choice `windows-native`; on native Windows use the
actual `Path.home()` and vault path without WSL conversion. Keep atomic merge/write behavior and
copy canonical skills to exactly the selected providers.

- [ ] **Step 4: Verify all global profiles GREEN**

Run: `python3 -m unittest -v tests.multiai_test`

Expected: existing portable/WSL installer tests plus native provider-neutral/idempotency test pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/install_global.py tests/multiai_test.py MULTI_AI.md
git commit -m "Support native Windows global agent connections"
```

---

### Task 8: Native Windows Fresh Installer and CI

**Files:**
- Create: `scripts/install-windows.ps1`
- Create: `SETUP-WINDOWS.md`
- Create: `tests/install_windows_test.ps1`
- Create: `tests/windows_native_test.py`
- Create: `.github/workflows/windows.yml`
- Modify: `.gitattributes`
- Modify: `.gitignore`

**Interfaces:**
- Produces PowerShell CLI: `install-windows.ps1 -VaultPath <path> -UserName <name> -UserBio <bio> -Companion <name> -OsName <name> -Providers <names> [-PreflightOnly]`
- Consumes: real Python 3, Git and at least one selected provider CLI.
- Produces: fresh stamped `2.0.0` / `1.1.0` native vault or no target mutation.

- [ ] **Step 1: Write PowerShell preflight and clean-install RED tests**

The tests create complete executable provider stubs before invoking the installer. Required cases:

- `-PreflightOnly` does not change a temp filesystem snapshot;
- Microsoft Store-style Python stub is rejected;
- Codex-only selected provider passes without Claude;
- missing every selected provider fails before target creation;
- clean install contains no `{{...}}`, `wsl.exe`, Bash or POSIX hook command;
- existing non-empty target exits `3` unchanged;
- generated adapter/rule merge is deterministic.

Run: `pwsh -NoProfile -File tests/install_windows_test.ps1`

Expected: missing installer failure.

- [ ] **Step 2: Write real native lifecycle/engine tests**

`tests/windows_native_test.py` uses temp vaults and executable CLI stubs to run bridge commands in
separate Windows Python processes. It covers all four provider command shapes, start/prompt/end/
precompact, concurrent counters, detached flush, provider-first retryable fallback and current-day
catch-up exclusion.

Run: `py.exe -3 -m unittest -v tests.windows_native_test`

Expected: native adapter/profile files are absent or fail before implementation.

- [ ] **Step 3: Implement the Windows bootstrap**

Keep preflight Windows PowerShell 5.1-compatible. Validate dependencies by executing version
probes; use .NET UTF-8 without BOM for any PowerShell-owned write. Delegate adapter generation and
verification to the installed Python scripts. Never invoke `winget`; print exact suggested commands
and stop for user authorization.

- [ ] **Step 4: Add deterministic Windows CI**

```yaml
name: windows-native
on:
  push:
    branches: [main]
  pull_request:
jobs:
  windows-native:
    runs-on: windows-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - shell: pwsh
        run: pwsh -NoProfile -File tests/install_windows_test.ps1
      - shell: pwsh
        run: py.exe -3 -m unittest -v tests.windows_native_test tests.runtime_platform_test
```

Use stable action majors supported by GitHub at implementation time; do not copy an unverified
future major solely because upstream used it.

- [ ] **Step 5: Run local syntax/tests and create the implementation commit**

Run:

```bash
python3 -m unittest -v tests.windows_native_test
git diff --check
```

```bash
git add scripts/install-windows.ps1 SETUP-WINDOWS.md tests/install_windows_test.ps1 tests/windows_native_test.py .github/workflows/windows.yml .gitattributes .gitignore
git commit -m "Add provider-neutral native Windows installation"
```

- [ ] **Step 6: Push once and require real Windows evidence**

Push the implementation commit to `main`, wait for the `windows-native` workflow, and inspect the
full failing step if CI is red. Fix failures with focused commits and rerun until green. A green
Linux simulation is not accepted as Windows evidence.

---

### Task 9: Documentation, Real Smoke Test and Release Gate

**Files:**
- Modify: `README.md`
- Modify: `SETUP.md`
- Modify: `MULTI_AI.md`
- Modify: `docs/SPEC-V2.md`
- Modify: `docs/beyin-v2.md`
- Modify: `docs/UPSTREAM-SYNC.md`
- Modify: `docs/superpowers/specs/2026-08-28-provider-neutral-windows-native-design.md` status only

**Interfaces:**
- Documents exactly three profiles and the native-v1 limitation.
- Records adopted upstream behavior and Respot-specific changes.

- [ ] **Step 1: Update public platform and install contracts**

Document:

- native Windows fresh install and existing Respot update commands;
- provider selection without Claude requirement;
- WSL remains verified and supported;
- native v1 conversion is refused and must use WSL;
- multi-AI `1.1.0` meaning;
- no scheduler/GUI and unchanged quota ownership;
- doctor/event log and backup remain subsequent projects.

- [ ] **Step 2: Run the full local release gate**

```bash
python3 -m unittest discover -s tests -p '*_test.py'
bash tests/hooks_test.sh
bash tests/upgrade_settings_test.sh
bash tests/upgrade_transaction_test.sh
python3 scripts/render_integrations.py --platform portable --check
git diff --check
```

Expected: zero failures, zero adapter drift and zero whitespace errors.

- [ ] **Step 3: Verify Windows CI and perform the real-machine smoke**

On the user's Windows machine, install a disposable native test vault with the user's selected
provider, run one real start/end session, confirm a new daily entry, then open with a second
installed provider and confirm SessionStart contains the first session context. Do not point the
smoke installer at `respectedOS`; keep the verified WSL production vault unchanged until the native
test passes.

- [ ] **Step 4: Mark spec implemented and update Respot memory**

Change spec status from `Proposed` to `Implemented`, record the final commit/workflow evidence in
`docs/UPSTREAM-SYNC.md`, and update respectedOS Last-Session/Threads with the result and remaining
native-v1 limitation.

- [ ] **Step 5: Final commit and push**

```bash
git add README.md SETUP.md MULTI_AI.md docs
git commit -m "Document provider-neutral native Windows support"
git push origin main
```

- [ ] **Step 6: Final verification report**

Report exact local test counts, Windows workflow URL/status, real smoke providers used, final
multi-AI stamp, backup location for any updated vault and the explicit deferred items: doctor/event
log, Restic backup and native v1 migration.
