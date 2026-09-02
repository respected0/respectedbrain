# Cross-Platform Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the confirmed Windows Native and Windows–WSL background-runtime failures for multi-AI 1.4.0 without changing provider selection, fallback, staging, or promotion security contracts.

**Architecture:** Keep `run_model()` as the single provider-neutral entry point while making each CLI invocation explicit about argv, stdin, permissions, and host compatibility. Put reusable host behavior in `runtime_platform.py`, keep transcript and output normalization at the hook/flush boundaries, and extend installers through explicit inputs rather than environment-wide guesses.

**Tech Stack:** Python 3 standard library, `unittest`, PowerShell 5.1-compatible scripting, Windows Task Scheduler (`schtasks.exe`), WSL interop, local Claude/Codex/Antigravity/Cursor CLIs.

**Spec:** `docs/superpowers/specs/2026-09-02-cross-platform-runtime-hardening-design.md`

## Global Constraints

- Preserve the configured provider → hook provider → existing `PROVIDERS` order.
- Advance fallback only for missing CLIs and existing retryable transient failures; authentication/configuration failures stop.
- Preserve `run_model(prompt, cwd, mode, timeout, preferred)` and its return tuple.
- Do not weaken compile staging, manifest validation, allowlists, symlink/reparse checks, or atomic promotion.
- Do not invent Cursor stdin behavior.
- Do not install into an additional home unless it is named explicitly.
- Keep Python and PowerShell changes compatible with the repository's existing supported platforms.

---

### Task 1: Host runtime primitives for hidden processes and WSL-accessible temp roots

**Files:**
- Modify: `template/.beyin/runtime_platform.py:84-92`
- Modify: `tests/runtime_platform_test.py`

**Interfaces:**
- Produces: `hidden_process_options() -> dict[str, int]`
- Produces: `windows_user_root(path: Path) -> Path | None`
- Produces: `external_temp_parent(vault_root: Path) -> Path | None`
- Consumed by: Tasks 2 and 3.

- [ ] **Step 1: Write failing runtime behavior tests**

Add tests that name the production breaks: synchronous Windows children opening a console, and a WSL vault choosing Linux `/tmp` for a Windows CLI stage.

```python
def test_hidden_process_options_are_empty_off_windows(self):
    with mock.patch.object(RUNTIME.os, "name", "posix"):
        self.assertEqual(RUNTIME.hidden_process_options(), {})

def test_hidden_process_options_use_create_no_window_on_windows(self):
    with mock.patch.object(RUNTIME.os, "name", "nt"), mock.patch.object(
        RUNTIME.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True
    ):
        self.assertEqual(
            RUNTIME.hidden_process_options(),
            {"creationflags": 0x08000000},
        )

def test_wsl_user_vault_selects_windows_accessible_temp_parent(self):
    vault = Path("/mnt/c/Users/Ada/Documents/Ada Brain")
    self.assertEqual(
        RUNTIME.external_temp_parent(vault),
        Path("/mnt/c/Users/Ada/AppData/Local/Temp"),
    )

def test_non_user_mount_and_native_windows_keep_system_temp(self):
    self.assertIsNone(RUNTIME.external_temp_parent(Path("/mnt/d/projects/brain")))
    with mock.patch.object(RUNTIME.os, "name", "nt"):
        self.assertIsNone(
            RUNTIME.external_temp_parent(Path(r"C:\Users\Ada\Ada Brain"))
        )
```

Import `mock` from `unittest` in the test file.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.runtime_platform_test.RuntimePlatformTest -v
```

Expected: failures because `hidden_process_options`, `windows_user_root`, and `external_temp_parent` do not exist.

- [ ] **Step 3: Implement the minimal runtime helpers**

Add focused helpers without changing `detached_process_options()`:

```python
def hidden_process_options() -> dict[str, int]:
    """Hide a synchronous child console on native Windows."""
    if os.name != "nt":
        return {}
    return {
        "creationflags": int(
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    }


def windows_user_root(path: Path) -> Path | None:
    """Return /mnt/<drive>/Users/<user> for a WSL-visible user path."""
    parts = Path(path).absolute().parts
    if (
        len(parts) < 5
        or parts[1] != "mnt"
        or len(parts[2]) != 1
        or parts[3].casefold() != "users"
    ):
        return None
    return Path(*parts[:5])


def external_temp_parent(vault_root: Path) -> Path | None:
    """Choose a temp parent usable by both WSL Python and Windows CLIs."""
    if os.name == "nt":
        return None
    user_root = windows_user_root(vault_root)
    if user_root is None:
        return None
    return user_root / "AppData" / "Local" / "Temp"
```

- [ ] **Step 4: Re-run the focused tests and confirm GREEN**

Run the command from Step 2. Expected: all runtime-platform tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add template/.beyin/runtime_platform.py tests/runtime_platform_test.py
git commit -m "fix: add cross-host runtime primitives"
```

---

### Task 2: Provider invocation transport, Windows environment, and provider-order regressions

**Files:**
- Modify: `template/.beyin/model_runner.py`
- Modify: `tests/multiai_test.py`

**Interfaces:**
- Consumes: `runtime_platform.hidden_process_options()` from Task 1.
- Produces: private immutable `Invocation(argv, stdin, windows_executable)`.
- Preserves: public `run_model()` signature and `(stdout, error, provider)` return value.

- [ ] **Step 1: Write failing command-contract tests**

Replace the Cursor-only structural test with behavioral coverage for all relevant providers. Patch executable discovery; assert large prompts never enter Codex or Antigravity argv.

```python
def test_runner_keeps_codex_and_antigravity_prompts_on_stdin(self):
    runner = load("model_runner_stdin", ROOT / "template/.beyin/model_runner.py")
    prompt = "ö" * 100_000

    def which(name):
        return {
            "codex": "/bin/codex",
            "agy": "/mnt/c/Users/Ada/AppData/Local/agy/bin/agy.exe",
        }.get(name)

    with mock.patch.object(runner.shutil, "which", side_effect=which):
        codex = runner._command("codex", prompt, "text")
        agy_text = runner._command("antigravity", prompt, "text")
        agy_workspace = runner._command("antigravity", prompt, "workspace")

    self.assertNotIn(prompt, codex.argv)
    self.assertEqual(codex.stdin, prompt)
    self.assertEqual(codex.argv[-1], "-")
    self.assertNotIn(prompt, agy_text.argv)
    self.assertEqual(agy_text.stdin, prompt)
    self.assertIn("--print", agy_text.argv)
    self.assertIn("--input-format", agy_text.argv)
    self.assertIn("--sandbox", agy_text.argv)
    self.assertNotIn("--mode", agy_text.argv)
    self.assertIn("--mode", agy_workspace.argv)
    self.assertIn("accept-edits", agy_workspace.argv)
    self.assertIn("--dangerously-skip-permissions", agy_workspace.argv)
    self.assertTrue(agy_workspace.windows_executable)
```

Keep the existing Cursor assertion but adapt it to `invocation.argv` and
`invocation.stdin`; it must still place the prompt in argv and return no stdin.

- [ ] **Step 2: Write failing provider-order and environment tests**

Add literal order assertions and a subprocess-call assertion that checks only
the required environment keys, never the whole inherited environment.

```python
def test_runner_candidate_order_contract_is_unchanged(self):
    runner = load("model_runner_order", ROOT / "template/.beyin/model_runner.py")
    with mock.patch.object(runner, "_configured_provider", return_value="auto"):
        self.assertEqual(
            runner._available("antigravity"),
            ["antigravity", "claude", "codex", "cursor"],
        )
    with mock.patch.object(runner, "_configured_provider", return_value="cursor"):
        self.assertEqual(
            runner._available("antigravity"),
            ["cursor", "antigravity", "claude", "codex"],
        )

def test_wsl_windows_cli_receives_translatable_profile_environment(self):
    runner = load("model_runner_wsl_env", ROOT / "template/.beyin/model_runner.py")
    invocation = runner.Invocation(["/mnt/c/bin/agy.exe", "--print"], "prompt", True)
    completed = SimpleNamespace(returncode=0, stdout="özet", stderr="")
    base = {"WSL_INTEROP": "/run/WSL/1_interop", "WSLENV": "PATH/l:KEEP"}
    with mock.patch.dict(runner.os.environ, base, clear=True), mock.patch.object(
        runner, "_command", return_value=invocation
    ), mock.patch.object(runner, "_available", return_value=["antigravity"]), mock.patch.object(
        runner.subprocess, "run", return_value=completed
    ) as called:
        result = runner.run_model(
            "prompt",
            Path("/mnt/c/Users/Ada/AppData/Local/Temp/stage"),
            "text",
            10,
        )
    self.assertEqual(result, ("özet", None, "antigravity"))
    environment = called.call_args.kwargs["env"]
    self.assertEqual(environment["USERPROFILE"], "/mnt/c/Users/Ada")
    self.assertEqual(environment["LOCALAPPDATA"], "/mnt/c/Users/Ada/AppData/Local")
    self.assertEqual(environment["APPDATA"], "/mnt/c/Users/Ada/AppData/Roaming")
    self.assertIn("USERPROFILE/p", environment["WSLENV"].split(":"))
    self.assertIn("KEEP", environment["WSLENV"].split(":"))
```

Use a patched module location or pass the accessible CWD into a helper so the
test derives `Ada` without mutating real paths. Add a traversal-free unit for
`_merge_wslenv()` that replaces `USERPROFILE` and `USERPROFILE/p` duplicates
with one `USERPROFILE/p` entry.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```bash
python3 -m unittest \
  tests.multiai_test.MultiAITest.test_runner_keeps_codex_and_antigravity_prompts_on_stdin \
  tests.multiai_test.MultiAITest.test_runner_candidate_order_contract_is_unchanged \
  tests.multiai_test.MultiAITest.test_wsl_windows_cli_receives_translatable_profile_environment -v
```

Expected: failures because `Invocation` and WSL environment preparation are absent and prompts remain in argv.

- [ ] **Step 4: Implement structured provider invocations**

Add:

```python
from dataclasses import dataclass

import runtime_platform


@dataclass(frozen=True)
class Invocation:
    argv: list[str]
    stdin: str | None
    windows_executable: bool = False


def _windows_executable(executable: str) -> bool:
    return os.name == "nt" or executable.casefold().endswith(".exe")
```

Return `Invocation` from `_command()`. Use these exact transports:

```python
# Codex
Invocation(
    [executable, "exec", "--ephemeral", "--sandbox", sandbox, "-"],
    prompt,
    _windows_executable(executable),
)

# Antigravity base
argv = [
    executable,
    "--new-project",
    "--disable-slash-commands",
    "--print",
    "--input-format", "text",
    "--output-format", "text",
    "--sandbox",
]
if mode == "workspace":
    argv[2:2] = [
        "--add-dir", ".",
        "--mode", "accept-edits",
        "--dangerously-skip-permissions",
    ]
return Invocation(argv, prompt, _windows_executable(executable))
```

Wrap the existing Claude and Cursor commands in `Invocation` without changing
their flags or model choices.

- [ ] **Step 5: Implement WSL profile environment preparation and hidden execution**

Add private helpers:

```python
def _merge_wslenv(value: str, path_names: tuple[str, ...]) -> str:
    targeted = {name.casefold() for name in path_names}
    kept = []
    for entry in value.split(":"):
        if not entry:
            continue
        base = entry.split("/", 1)[0].casefold()
        if base not in targeted:
            kept.append(entry)
    kept.extend(f"{name}/p" for name in path_names)
    return ":".join(kept)


def _windows_user_environment(environment: dict[str, str], cwd: Path) -> None:
    if os.name == "nt" or not environment.get("WSL_INTEROP"):
        return
    user_root = runtime_platform.windows_user_root(cwd)
    if user_root is None:
        user_root = runtime_platform.windows_user_root(Path(__file__).resolve())
    if user_root is None:
        return
    environment["USERPROFILE"] = str(user_root)
    environment["LOCALAPPDATA"] = str(user_root / "AppData/Local")
    environment["APPDATA"] = str(user_root / "AppData/Roaming")
    names = ("USERPROFILE", "LOCALAPPDATA", "APPDATA")
    environment["WSLENV"] = _merge_wslenv(environment.get("WSLENV", ""), names)
```

Call it only for `Invocation.windows_executable`. Pass
`**runtime_platform.hidden_process_options()` to `subprocess.run()`. Keep the
existing timeout, retry classification, and non-retryable early return.

- [ ] **Step 6: Re-run focused and complete multi-AI tests**

Run:

```bash
python3 -m unittest tests.multiai_test -v
```

Expected: all MultiAITest cases pass, including existing retryable/non-retryable fallback tests.

- [ ] **Step 7: Commit Task 2**

```bash
git add template/.beyin/model_runner.py tests/multiai_test.py
git commit -m "fix: harden provider invocation transport"
```

---

### Task 3: Windows-accessible flush/compile staging

**Files:**
- Modify: `template/.claude/scripts/flush.py:325-375`
- Modify: `template/.claude/scripts/compile.py:317-359`
- Modify: `tests/scripts_test.py`
- Modify: `tests/windows_native_test.py`

**Interfaces:**
- Consumes: `runtime_platform.external_temp_parent(vault_root)` from Task 1.
- Preserves: stage location outside the vault, mode `0700` on POSIX, cleanup, and allowlisted promotion.

- [ ] **Step 1: Write failing temp-parent tests**

Add direct tests around new small wrappers rather than relying on real Windows
processes:

```python
def test_flush_temp_directory_uses_cross_host_parent(self):
    expected = self.root / "windows-temp"
    expected.mkdir()
    with mock.patch.object(
        FLUSH.runtime_platform, "external_temp_parent", return_value=expected
    ):
        kwargs = FLUSH._temporary_directory_kwargs(self.vault)
    self.assertEqual(kwargs, {"dir": expected})

def test_compile_stage_uses_cross_host_parent_and_remains_external(self):
    compiler = load_module("compile_temp_parent", SOURCE_SCRIPTS / "compile.py")
    expected = self.root / "windows-temp"
    expected.mkdir()
    with mock.patch.object(
        compiler.runtime_platform, "external_temp_parent", return_value=expected
    ):
        stage, _baseline = compiler._prepare_stage(
            self.vault,
            self.state,
            self.daily / "2026-08-20.md",
        )
    try:
        self.assertEqual(stage.parent, expected)
        self.assertFalse(stage.is_relative_to(self.vault))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
```

Create the daily fixture and required knowledge files before `_prepare_stage()`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run the two new test methods. Expected: failures because `_temporary_directory_kwargs()` does not exist and `_prepare_stage()` always uses system temp.

- [ ] **Step 3: Implement minimal temp-parent routing**

In both scripts add:

```python
def _temporary_directory_kwargs(vault_root: Path) -> dict[str, Path]:
    parent = runtime_platform.external_temp_parent(vault_root)
    if parent is None:
        return {}
    parent.mkdir(parents=True, exist_ok=True)
    return {"dir": parent}
```

Use it in `TemporaryDirectory(prefix="beyin-flush-", **kwargs)` and
`tempfile.mkdtemp(prefix="compile-stage-", **kwargs)`. Do not change stage
permissions, copy policy, manifest generation, promotion, or cleanup.

- [ ] **Step 4: Re-run scripts and native structural tests**

Run:

```bash
python3 -m unittest tests.scripts_test tests.windows_native_test -v
```

Expected: portable tests pass; native-only tests remain skipped off Windows.

- [ ] **Step 5: Commit Task 3**

```bash
git add template/.claude/scripts/flush.py template/.claude/scripts/compile.py tests/scripts_test.py tests/windows_native_test.py
git commit -m "fix: keep WSL model stages Windows-accessible"
```

---

### Task 4: Antigravity transcript discovery and robust summary/compile contracts

**Files:**
- Modify: `template/.beyin/hooks/bridge.py:41-82`
- Modify: `template/.claude/scripts/flush.py:211-241,609-650`
- Modify: `template/.claude/scripts/compile.py:47-96`
- Modify: `tests/multiai_test.py`
- Modify: `tests/scripts_test.py`

**Interfaces:**
- Produces: `resolve_antigravity_transcript(session_id: str, home: Path | None = None) -> str`
- Produces: `normalize_summary(summary: str) -> str | None`
- Preserves: explicit transcript precedence and strict five-heading schema.

- [ ] **Step 1: Write failing transcript resolver tests**

```python
def test_antigravity_normalize_resolves_ide_then_cli_transcript(self):
    bridge = load("bridge_transcript", ROOT / "template/.beyin/hooks/bridge.py")
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        ide = home / ".gemini/antigravity-ide/brain/session-1/.system_generated/logs/transcript.jsonl"
        ide.parent.mkdir(parents=True)
        ide.write_text("{}\n", encoding="utf-8")
        with mock.patch.object(bridge.Path, "home", return_value=home):
            normalized = bridge.normalize("antigravity", {"conversationId": "session-1"})
        self.assertEqual(normalized["transcript_path"], str(ide))

def test_antigravity_transcript_discovery_rejects_traversal(self):
    bridge = load("bridge_transcript_traversal", ROOT / "template/.beyin/hooks/bridge.py")
    with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
        bridge.Path, "home", return_value=Path(temporary)
    ):
        normalized = bridge.normalize("antigravity", {"conversationId": "../escape"})
    self.assertEqual(normalized["transcript_path"], "")
```

Also assert an explicit payload path wins even when a discovered file exists.

- [ ] **Step 2: Write failing summary normalization tests**

```python
def test_summary_normalization_drops_conversational_preamble(self):
    raw = "Selam! İşte özet:\n```markdown\n" + VALID_SUMMARY + "\n```"
    self.assertEqual(FLUSH.normalize_summary(raw), VALID_SUMMARY)

def test_summary_normalization_rejects_extra_or_wrong_level_headings(self):
    self.assertIsNone(FLUSH.normalize_summary(VALID_SUMMARY + "\n## Fazla\nHayır"))
    self.assertIsNone(
        FLUSH.normalize_summary(VALID_SUMMARY.replace("## Öğrenilenler", "### Öğrenilenler"))
    )
    self.assertIsNone(
        FLUSH.normalize_summary("## Açıklama\nSohbet\n" + VALID_SUMMARY)
    )
```

Extend the existing end-to-end flush test so a preamble-wrapped valid response
is appended without the preamble or fences.

- [ ] **Step 3: Run focused tests and confirm RED**

Run the new resolver and normalization methods. Expected: transcript remains empty and `normalize_summary` is absent.

- [ ] **Step 4: Implement safe bounded transcript resolution**

Add a strict component expression and resolver:

```python
SESSION_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def resolve_antigravity_transcript(
    session_id: str,
    home: Path | None = None,
) -> str:
    if SESSION_COMPONENT.fullmatch(session_id) is None or session_id in {".", ".."}:
        return ""
    profile = home or Path.home()
    for product in ("antigravity-ide", "antigravity-cli"):
        brain = profile / ".gemini" / product / "brain"
        candidate = brain / session_id / ".system_generated/logs/transcript.jsonl"
        try:
            candidate.resolve(strict=True).relative_to(brain.resolve(strict=True))
        except (OSError, RuntimeError, ValueError):
            continue
        if candidate.is_file():
            return str(candidate)
    return ""
```

In `normalize()`, resolve only when the explicit path is empty and provider is
Antigravity.

- [ ] **Step 5: Implement summary normalization and prompt hardening**

Add a direct output instruction before the untrusted transcript. Implement:

```python
def normalize_summary(summary: str) -> str | None:
    stripped = summary.strip()
    if stripped == "FLUSH_BOS":
        return stripped
    start = re.search(r"(?m)^## Bağlam\s*$", stripped)
    if start is None:
        return None
    prefix = stripped[:start.start()].strip()
    for fence in ("```markdown", "```"):
        if prefix.endswith(fence):
            prefix = prefix[:-len(fence)].strip()
            break
    if HEADING.search(prefix) or "```" in prefix:
        return None
    candidate = stripped[start.start():].strip()
    if candidate.endswith("```"):
        candidate = candidate[:-3].rstrip()
    return candidate if validate_summary(candidate) else None
```

Call this once after `_run_model()`. Use its returned content for `FLUSH_BOS`
and `_append_daily`; record `summary-schema-invalid` when it returns `None`.
Keep `validate_summary()` strict.

Prepend the compile prompt with this operational requirement:

```text
OTOMATİK DERLEYİCİ ROLÜ
Bu başsız bir workspace görevidir. Başarı için aşağıdaki izinli stage dosyalarını
araçlarla düzenle; sohbet açıklaması tek başına başarı değildir.
```

- [ ] **Step 6: Re-run hook and engine suites**

Run:

```bash
python3 -m unittest tests.multiai_test tests.scripts_test -v
bash tests/hooks_test.sh
```

Expected: new cases and all existing security/promotion tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add template/.beyin/hooks/bridge.py template/.claude/scripts/flush.py template/.claude/scripts/compile.py tests/multiai_test.py tests/scripts_test.py
git commit -m "fix: recover Antigravity transcripts and model output"
```

---

### Task 5: WSL-safe Windows Task Scheduler XML paths

**Files:**
- Modify: `scripts/install_briefing_schedule.py:248-294,297-355`
- Modify: `tests/briefing_schedule_test.py`

**Interfaces:**
- Produces: `_windows_argument_path(path: Path) -> str`
- Changes private call: `_create_windows_task(name, content, home)`.
- Preserves: task verification, legacy deletion ordering, backup, and rollback.

- [ ] **Step 1: Write failing Windows-path tests**

```python
def test_wsl_task_xml_is_created_under_home_and_passed_as_windows_path(self):
    installer = load_installer()
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary) / "mounted-home"
        home.mkdir()
        completed = mock.Mock(returncode=0, stdout=b"", stderr=b"")

        def command(argv, **kwargs):
            if argv[0] == "wslpath":
                source = argv[-1]
                self.assertTrue(str(home) in source)
                return mock.Mock(returncode=0, stdout="C:\\Users\\Ada\\task.xml\n", stderr="")
            self.assertEqual(argv[0], "schtasks.exe")
            self.assertEqual(argv[argv.index("/XML") + 1], r"C:\Users\Ada\task.xml")
            return completed

        with mock.patch.object(installer.subprocess, "run", side_effect=command):
            result = installer._create_windows_task("task", "<Task />", home)
    self.assertIs(result, completed)
```

Add a native-path unit that patches `_windows_argument_path()` or `os.name` and
asserts a Windows path is returned unchanged without calling `wslpath`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run the two new tests. Expected: `_create_windows_task` rejects the `home` argument and uses system temp/string path directly.

- [ ] **Step 3: Implement WSL path conversion**

```python
def _windows_argument_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return str(path)
    converted = result.stdout.strip()
    return converted if result.returncode == 0 and converted else str(path)
```

Create the UTF-16 XML with `dir=home`, pass the converted path to `schtasks`,
and thread `home` through create and restore calls. Keep subprocess output in
bytes for the existing decoders.

- [ ] **Step 4: Re-run all scheduler tests**

```bash
python3 -m unittest tests.briefing_schedule_test -v
```

Expected: all scheduler tests pass, including Turkish OEM decoding and migration ordering.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/install_briefing_schedule.py tests/briefing_schedule_test.py
git commit -m "fix: translate WSL scheduler XML paths"
```

---

### Task 6: Finite native Windows installer probes

**Files:**
- Modify: `scripts/install-windows.ps1:49-63`
- Modify: `tests/install_windows_test.ps1`

**Interfaces:**
- Preserves: `Invoke-ExternalProbe` result shape `{ Code; Output }`.
- Adds: environment-overridable test timeout `RESPECTED_PROBE_TIMEOUT_MS`; production default 15,000 ms.

- [ ] **Step 1: Write a failing PowerShell integration test for a hanging provider**

Add a provider stub:

```powershell
$HangingCommands = Join-Path $Root "hanging-commands"
New-ProviderStub $HangingCommands "git"
[IO.File]::WriteAllText(
    (Join-Path $HangingCommands "codex.cmd"),
    "@echo off`r`nping 127.0.0.1 -n 30 >nul`r`nexit /b 0`r`n",
    [Text.UTF8Encoding]::new($false)
)
$env:RESPECTED_TEST_COMMAND_ROOT = $HangingCommands
$env:RESPECTED_PROBE_TIMEOUT_MS = "200"
$Stopwatch = [Diagnostics.Stopwatch]::StartNew()
$timed = Invoke-Installer @(
    "-VaultPath", (Join-Path $Root "timeout-vault"),
    "-UserName", "Ada", "-UserBio", "Geliştirici",
    "-Companion", "Echo", "-OsName", "AdaOS",
    "-Providers", "codex", "-PreflightOnly"
)
$Stopwatch.Stop()
Assert-True ($timed.Code -ne 0) "Takılan provider probe başarısız olmalı"
Assert-True ($Stopwatch.Elapsed.TotalSeconds -lt 5) "Probe timeout kurulumu bloklamamalı"
Remove-Item Env:RESPECTED_PROBE_TIMEOUT_MS
```

Restore `$env:RESPECTED_TEST_COMMAND_ROOT` after the case and clean the timeout
environment variable in `finally`.

- [ ] **Step 2: Run the PowerShell test and confirm RED on Windows**

Run:

```powershell
powershell -NoProfile -File tests\install_windows_test.ps1
```

Expected before the fix: the case takes roughly 30 seconds instead of returning within five seconds.

- [ ] **Step 3: Implement bounded `Start-Process` waiting**

Keep file capture and `.cmd/.bat/.exe` compatibility:

```powershell
function Invoke-ExternalProbe([string]$Command, [string[]]$Arguments) {
    $stdout = [IO.Path]::GetTempFileName()
    $stderr = [IO.Path]::GetTempFileName()
    $TimeoutMs = 15000
    if ($env:RESPECTED_PROBE_TIMEOUT_MS) {
        $ParsedTimeout = 0
        if ([int]::TryParse($env:RESPECTED_PROBE_TIMEOUT_MS, [ref]$ParsedTimeout) -and $ParsedTimeout -gt 0) {
            $TimeoutMs = $ParsedTimeout
        }
    }
    try {
        $ArgumentList = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
        $Process = Start-Process -FilePath $Command -ArgumentList $ArgumentList -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        if (-not $Process.WaitForExit($TimeoutMs)) {
            try { $Process.Kill() } catch {}
            $Process.WaitForExit()
            return @{ Code = 124; Output = ([IO.File]::ReadAllText($stdout) + [IO.File]::ReadAllText($stderr) + "probe-timeout") }
        }
        return @{ Code = $Process.ExitCode; Output = ([IO.File]::ReadAllText($stdout) + [IO.File]::ReadAllText($stderr)) }
    }
    finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}
```

- [ ] **Step 4: Run the complete native installer test on Windows**

Run the command from Step 2. Expected: all existing and timeout assertions pass.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/install-windows.ps1 tests/install_windows_test.ps1
git commit -m "fix: bound Windows installer probes"
```

---

### Task 7: Explicit multi-home Antigravity global installation

**Files:**
- Modify: `scripts/install_global.py`
- Modify: `scripts/install_antigravity_global.py`
- Modify: `tests/multiai_test.py`
- Modify: `README.md`
- Modify: `MULTI_AI.md`
- Modify: `SETUP.md`

**Interfaces:**
- Adds CLI: repeatable `--antigravity-home <path>`.
- Preserves: existing single `--home`, provider selection, preview, backup, and idempotency.

- [ ] **Step 1: Write failing two-home installer tests**

Add an end-to-end test using two temporary homes:

```python
def test_global_installer_can_manage_explicit_windows_and_wsl_antigravity_homes(self):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        vault = root / "Ada Brain"
        shutil.copytree(ROOT / "template", vault)
        primary = root / "windows-home"
        wsl = root / "wsl-home"
        primary.mkdir()
        wsl.mkdir()
        command = [
            sys.executable,
            str(ROOT / "scripts/install_global.py"),
            str(vault),
            "--home", str(primary),
            "--platform", "windows-wsl",
            "--providers", "all",
            "--antigravity-home", str(wsl),
            "--apply",
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue((primary / ".gemini/config/hooks.json").is_file())
        self.assertTrue((wsl / ".gemini/config/hooks.json").is_file())
        self.assertTrue((primary / ".codex/hooks.json").is_file())
        self.assertFalse((wsl / ".codex").exists())
        before = {
            (home.name, path.relative_to(home)): path.read_bytes()
            for home in (primary, wsl)
            for path in home.rglob("*") if path.is_file() and ".respected-backups" not in path.parts
        }
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        after = {
            (home.name, path.relative_to(home)): path.read_bytes()
            for home in (primary, wsl)
            for path in home.rglob("*") if path.is_file() and ".respected-backups" not in path.parts
        }
        self.assertEqual(after, before)
```

Add a preview test proving neither home changes, a duplicate-home
de-duplication assertion, and an error case for a nonexistent additional home.

- [ ] **Step 2: Run focused tests and confirm RED**

Run the new MultiAITest methods. Expected: argparse rejects `--antigravity-home`.

- [ ] **Step 3: Extend `install_global.py` planning and application**

Add:

```python
parser.add_argument(
    "--antigravity-home",
    action="append",
    default=[],
    type=Path,
    help="ek Antigravity kullanıcı kökü; birden fazla verilebilir",
)
```

Resolve and de-duplicate homes by their resolved path. Build the primary plan
with the requested provider set. For each additional home, require that
Antigravity is selected and call `build(vault, extra_home,
("antigravity",), platform)`. Preview every target grouped by home.

On apply, call `apply_plan()` once per home with that home's backup root:

```python
backup = home / ".respected-backups" / timestamp
apply_plan(writes, home, backup)
```

If a home's application fails, rely on `apply_plan()` to roll back that home,
report the exact home, and return nonzero. Do not delete a previously successful
home or merge backups across home roots.

- [ ] **Step 4: Extend the compatibility Antigravity installer**

Change its argument to `action="append", required=True`; resolve and
de-duplicate the values, preview each home, and independently call the same
`build()`/`apply_plan()` path for each.

- [ ] **Step 5: Document the Connect-to-WSL pairing**

Add one concrete command to README, MULTI_AI, and the Windows–WSL setup section:

```bash
python3 scripts/install_global.py "/mnt/c/Users/<windows-user>/Documents/<vault>" \
  --home "/mnt/c/Users/<windows-user>" \
  --antigravity-home "/home/<wsl-user>" \
  --platform windows-wsl --providers all --apply
```

Explain that `--home` is the Windows profile and the explicit additional home
is used when Antigravity Connect to WSL reads Linux-side `.gemini` state.

- [ ] **Step 6: Re-run full multi-AI tests**

```bash
python3 -m unittest tests.multiai_test -v
```

Expected: all old single-home and new multi-home cases pass.

- [ ] **Step 7: Commit Task 7**

```bash
git add scripts/install_global.py scripts/install_antigravity_global.py tests/multiai_test.py README.md MULTI_AI.md SETUP.md
git commit -m "feat: support explicit Antigravity profile homes"
```

---

### Task 8: Regenerate managed copies and complete release verification

**Files:**
- Regenerate: `template/scripts/install_briefing_schedule.py`
- Regenerate: `template/scripts/install_global.py`
- Regenerate: `template/scripts/install_antigravity_global.py`
- Modify only if generated by canonical renderer: integration artifacts reported by `render_integrations.py`

**Interfaces:**
- Consumes: all preceding tasks.
- Produces: drift-free template artifacts and verification evidence.

- [ ] **Step 1: Regenerate canonical template helpers**

Run:

```bash
python3 scripts/render_integrations.py
```

Review `git diff --stat` and `git diff`; only canonical generated copies and
expected profile artifacts may change.

- [ ] **Step 2: Verify renderer drift is clean**

```bash
python3 scripts/render_integrations.py --check
```

Expected: exit 0 and no reported paths.

- [ ] **Step 3: Run the portable Python suite**

```bash
python3 -m unittest discover -s tests -p '*_test.py' -v
```

Expected: all portable tests pass; native-Windows-only cases are explicitly skipped off Windows.

- [ ] **Step 4: Run shell lifecycle and updater tests**

```bash
bash tests/hooks_test.sh
bash tests/upgrade_settings_test.sh
bash tests/upgrade_transaction_test.sh
```

Expected: all three scripts exit 0.

- [ ] **Step 5: Run native PowerShell suites on Windows**

```powershell
powershell -NoProfile -File tests\install_windows_test.ps1
powershell -NoProfile -File tests\briefing_schedule_windows_test.ps1
```

Expected: both suites report OK. If the current host cannot execute them, record
that limitation without claiming native verification.

- [ ] **Step 6: Run static repository gates**

```bash
git diff --check
git status --short
python3 -m unittest tests.naming_contract_test tests.profile_render_test -v
```

Expected: no whitespace errors, only intended files changed, and naming/render contracts pass.

- [ ] **Step 7: Commit generated artifacts**

```bash
git add template/scripts template/.agents template/.claude/settings.json template/.codex template/.cursor
git commit -m "chore: regenerate runtime integration artifacts"
```

- [ ] **Step 8: Perform completion verification before any success claim**

Invoke `superpowers:verification-before-completion`, re-run its required fresh
commands, inspect the outputs, and report exact pass/skip counts. Do not stamp
1.4.0 or modify updater manifests unless Furkan explicitly starts the release
task after these fixes are verified.
