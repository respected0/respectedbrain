"""Readonly plans for explicit vault/provider contexts and stable installed launchers."""
from __future__ import annotations
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from .backend import ExternalChange, IntegrationProfile, canonical_json
from .global_config import *
from respectedbrain.core.errors import FoundationError, OwnershipConflict
from respectedbrain.core.platform import path_within_vault

def wsl_path(path):
    value = str(path).replace("\\", "/")
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/mnt/{value[0].lower()}/{value[3:]}"
    return value

def _runtime_path(path, platform):
    return wsl_path(path) if platform == "windows-wsl" else str(path)

def validate_profile(ctx, profile):
    if not profile.user_home.is_absolute() or not profile.user_home.is_dir():
        raise ValueError("Explicit provider home must be an existing absolute directory")
    if not profile.launcher or any(not isinstance(p, str) or not p for p in profile.launcher):
        raise ValueError("Explicit installed launcher is required")
    executable = Path(profile.launcher[0]).name.casefold()
    if re.fullmatch(r"(?:py|python(?:[0-9]+(?:\.[0-9]+)*)?)(?:\.exe)?", executable) or any(item.endswith(".py") for item in profile.launcher):
        raise ValueError("Persistent registrations require the installed application launcher")
    if profile.platform == "windows-native":
        if profile.launcher != (str(ctx.paths.app_root / "respectedbrain.exe"),):
            raise ValueError("Native registrations require the stable AppRoot executable")
    elif profile.platform == "windows-wsl":
        script = 'if [ "${1#/}" != "$1" ]; then test -x "$1"; else command -v "$1" >/dev/null; fi'
        result = subprocess.run(["wsl.exe", "--", "sh", "-c", script, "respectedbrain", profile.launcher[0]], capture_output=True, timeout=15)
        if result.returncode:
            raise FoundationError("WSL launcher was not executable inside WSL")
        command = ["wsl.exe", "--", *profile.launcher, "vault", "list"]
        registered = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=15)
        diagnosis = "WSL configuration conflict: Linux DataRoot must register the same vault UUID. Run inside WSL: " + shlex.join([*profile.launcher, "vault", "register", wsl_path(ctx.paths.vault_root)])
        try:
            document = json.loads(registered.stdout) if registered.returncode == 0 else {}
            entry = document.get(ctx.paths.vault_id) if isinstance(document, dict) else None
            recorded = entry.get("path") if isinstance(entry, dict) else None
            expected = wsl_path(ctx.paths.vault_root)
            if not isinstance(recorded, str) or recorded.rstrip("/") != expected.rstrip("/"):
                raise OwnershipConflict(diagnosis)
        except (ValueError, TypeError) as error:
            raise OwnershipConflict(diagnosis) from error
    elif profile.platform != "posix":
        raise ValueError("Unsupported integration platform")

def launch_argv(ctx, profile, command, *args):
    argv = [*profile.launcher, command, "--vault-id", ctx.paths.vault_id, *args]
    if profile.platform == "windows-wsl":
        return ["wsl.exe", "--cd", wsl_path(ctx.paths.vault_root), *argv]
    return argv

def bridge_argv(ctx, profile, provider, event, *, global_hook=False):
    return launch_argv(ctx, profile, "hook", "--provider", provider, "--event", event, *(["--global-hook"] if global_hook else []))

def command_text(profile, argv):
    return subprocess.list2cmdline(argv) if profile.platform.startswith("windows") else shlex.join(argv)

class _Planner:
    def __init__(self, backend):
        self.backend = backend
        self.before = {}
        self.after = {}
    def read(self, path, kind="file"):
        identity = (kind, str(path))
        if identity not in self.before:
            self.before[identity] = self.backend.read(*identity)
        return self.before[identity]
    def text(self, path):
        return (self.read(path) or b"").decode("utf-8-sig")
    def object(self, path, kind="file"):
        data = self.read(path, kind)
        value = json.loads(data) if data is not None else {}
        if not isinstance(value, dict):
            raise ValueError(f"{path} is not a JSON object")
        return value
    def put(self, kind, key, after):
        identity = (kind, str(key))
        self.read(key, kind)
        if isinstance(after, str):
            after = after.encode("utf-8")
        if identity in self.after and self.after[identity] != after:
            raise OwnershipConflict(f"Conflicting planned registration: {key}")
        self.after[identity] = after
    def changes(self):
        return tuple(ExternalChange(kind, key, self.before[(kind, key)], after) for (kind, key), after in self.after.items() if self.before[(kind, key)] != after)

def managed_rule(ctx):
    override = ctx.paths.overrides_dir / "instructions.md"
    nested = ctx.paths.overrides_dir / "instructions/default.md"
    if any(not path_within_vault(path, ctx.paths.data_root) for path in (override, nested)):
        raise OwnershipConflict('Unsafe instruction override')
    if override.is_file():
        instructions = override.read_text(encoding="utf-8").strip()
    elif nested.is_file():
        instructions = nested.read_text(encoding="utf-8").strip()
    else:
        instructions = ctx.resources.read_text("instructions/default.md").strip()
    vault = ctx.paths.vault_root
    replacements = identity_settings(ctx)
    for key, value in replacements.items():
        instructions = instructions.replace("{{" + key + "}}", str(value))
    win = windows_path(vault)
    locations = f"`{vault}`" + (f" (Windows: `{win}`)" if win else "")
    return f"{BEGIN}\n# Global ikinci beyin bağlantısı\n\nKalıcı hafıza vault'u **{vault.name}**: {locations}.\nGöreceli hafıza yollarını aktif kod reposuna göre değil bu vault köküne göre çöz. Kullanıcı istemedikçe proje kodunu vault'a taşıma.\n\n{instructions}\n{END}"

def skill_writes(ctx, roots):
    contents = {name: ctx.resources.read_text("skills/" + name) for name in ctx.resources.iter_files("skills") if name.endswith("/SKILL.md")}
    override = ctx.paths.overrides_dir / "skills"
    if not path_within_vault(override, ctx.paths.data_root):
        raise OwnershipConflict('Unsafe skill override directory')
    if override.is_dir():
        for path in override.glob("*/SKILL.md"):
            if not path_within_vault(path, ctx.paths.data_root):
                raise OwnershipConflict("Skill override has a link/reparse point")
            contents[path.relative_to(override).as_posix()] = path.read_text(encoding="utf-8")
    return [(base / name, content) for name, content in sorted(contents.items()) for base in roots]

def _recorded_or_legacy_owner(ctx, planner, path, current, kind="file"):
    proofs = getattr(planner.backend, "_legacy_proofs", {})
    if isinstance(proofs, dict) and proofs.get((kind, str(path))) == current:
        return True
    payload = planner.read(ctx.paths.data_root / "install-manifest.json")
    if payload is None:
        return False
    import base64
    try:
        document = json.loads(payload)
        if document.get("schema_version") != 3:
            raise ValueError("manifest schema")
        return any(row.get("kind") == kind and row.get("key") == str(path) and row.get("after") is not None and base64.b64decode(row["after"], validate=True) == current for row in document.get("external", []))
    except (ValueError, TypeError, AttributeError) as error:
        raise OwnershipConflict("Invalid integration ownership manifest") from error


def _assert_owned_replacement(ctx, planner, path, baseline, *, kind="file"):
    current = planner.read(path, kind)
    if current is not None and current != baseline and not _recorded_or_legacy_owner(ctx, planner, path, current, kind):
        raise OwnershipConflict(f"Unowned or user-changed integration file: {path}")


def _global_writes(ctx, profile, planner, providers=SUPPORTED) -> tuple[list[tuple[Path, str | None]], list[Path]]:
    writes: list[tuple[Path, str | None]] = []
    touched: list[Path] = []
    vault, home, platform = ctx.paths.vault_root, profile.user_home, profile.platform
    rule = managed_rule(ctx)
    def load_object(path):
        document = planner.object(path)
        current = planner.read(path)
        if current is None:
            return document
        owned = _recorded_or_legacy_owner(ctx, planner, path, current)
        expected = {command_text(profile, bridge_argv(ctx, profile, provider, event, global_hook=True)) for provider in SUPPORTED for event in ("start", "prompt", "turn", "end", "precompact", "postcompact", "notify")}
        def check(value, namespace=False):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "command" and isinstance(item, str) and (namespace or "--global-hook" in item):
                        if item not in expected and not owned:
                            raise OwnershipConflict(f"Unknown managed hook command: {path}")
                    else:
                        check(item, namespace or key in {HOOK_NAME, LEGACY_HOOK_NAME})
            elif isinstance(value, list):
                for item in value:
                    check(item, namespace)
        check(document)
        return document
    def bridge_command(vault, provider, event, platform):
        return command_text(profile, bridge_argv(ctx, profile, provider, event, global_hook=True))
    def codex_notify_argv(vault, platform):
        return bridge_argv(ctx, profile, "codex", "notify")
    def _managed_codex_notify(argv):
        if not argv:
            return False
        expected = codex_notify_argv(vault, platform)
        proofs = getattr(planner.backend, "_legacy_proofs", {})
        proven = isinstance(proofs, dict) and proofs.get(("file", str(home / ".codex/config.toml"))) == planner.read(home / ".codex/config.toml")
        return argv[:len(expected)] == expected or proven
    def copy_skills(vault, roots):
        writes = skill_writes(ctx, roots)
        for target, _content in writes:
            relative = next(target.relative_to(base).as_posix() for base in roots if target.is_relative_to(base))
            try:
                baseline = ctx.resources.read_text("skills/" + relative).encode("utf-8")
            except FileNotFoundError:
                baseline = None
            _assert_owned_replacement(ctx, planner, target, baseline)
        return writes

    if "antigravity" in providers:
        config = home / ".gemini/config"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        if LEGACY_HOOK_NAME in hooks and HOOK_NAME in hooks:
            raise ValueError("legacy ve current Antigravity hook anahtarları çakışıyor")
        hooks.pop(LEGACY_HOOK_NAME, None)
        hooks[HOOK_NAME] = {
            "PreInvocation": [{"type": "command", "command": bridge_command(vault, "antigravity", "start", platform), "timeout": 15}],
            "Stop": [{"type": "command", "command": bridge_command(vault, "antigravity", "turn", platform), "timeout": 10}],
        }
        rule_path = home / ".gemini/GEMINI.md"
        writes += [(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"), (rule_path, merge_managed(planner.text(rule_path), rule))]
        writes += copy_skills(vault, [config / "skills"])
        touched += [hooks_path, rule_path]

    if "gemini" in providers:
        config = home / ".gemini"
        settings_path = config / "settings.json"
        settings = load_object(settings_path)
        commands = {
            "SessionStart": (bridge_command(vault, "gemini", "start", platform), 15000),
            "BeforeAgent": (bridge_command(vault, "gemini", "prompt", platform), 5000),
            "AfterAgent": (bridge_command(vault, "gemini", "turn", platform), 10000),
            "SessionEnd": (bridge_command(vault, "gemini", "end", platform), 10000),
            "PreCompress": (bridge_command(vault, "gemini", "precompact", platform), 10000),
        }
        merge_gemini_hooks(settings, commands)
        rule_path = config / "GEMINI.md"
        writes += [
            (settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n"),
            (
                rule_path,
                merge_managed(
                    planner.text(rule_path),
                    rule,
                ),
            ),
        ]
        writes += copy_skills(vault, [config / "skills"])
        touched += [settings_path, rule_path]

    if "codex" in providers:
        config = home / ".codex"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        commands = {
            "SessionStart": (bridge_command(vault, "codex", "start", platform), 15),
            "UserPromptSubmit": (bridge_command(vault, "codex", "prompt", platform), 5),
            "SessionEnd": (bridge_command(vault, "codex", "end", platform), 3),
            "Stop": (bridge_command(vault, "codex", "turn", platform), 10),
            "PreCompact": (bridge_command(vault, "codex", "precompact", platform), 10),
        }
        merge_grouped_hooks(hooks, "codex", commands)
        hooks_path_content = json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"
        rule_path = config / "AGENTS.md"
        writes += [(hooks_path, hooks_path_content), (rule_path, merge_managed(planner.text(rule_path), rule))]
        writes += copy_skills(vault, [home / ".agents/skills"])
        touched += [hooks_path, rule_path]

        config_toml_path = config / "config.toml"
        notify_cmd = codex_notify_argv(vault, platform)
        existing_toml = planner.text(config_toml_path)
        existing_notify = parse_codex_notify_argv(existing_toml)
        if re.search(r"(?m)^notify\s*=", existing_toml) and existing_notify is None:
            raise ValueError(
                "Codex notify ayarı güvenle ayrıştırılamadı; config.toml içindeki notify "
                "dizisini tek satıra getirip yeniden deneyin"
            )
        chain_path = ctx.paths.state_dir / "codex-notify-chain.json"
        if existing_notify and not _managed_codex_notify(existing_notify):
            notify_cmd += ["--chain-file", _runtime_path(chain_path, platform)]
            writes += [(chain_path, json.dumps({"argv": existing_notify}, ensure_ascii=False, indent=2) + "\n")]
            touched += [chain_path]
        elif existing_notify and "--chain-file" in existing_notify and planner.read(chain_path) is None:
            index = existing_notify.index("--chain-file")
            if index + 1 >= len(existing_notify):
                raise OwnershipConflict("Existing Codex notify chain is incomplete")
            legacy_chain = Path(existing_notify[index + 1])
            if legacy_chain.resolve() != (home / ".codex/respected-notify-chain.json").resolve():
                raise OwnershipConflict("Existing Codex notify chain belongs to an unknown path")
            chain = load_object(legacy_chain)
            chain_argv = chain.get("argv")
            if not isinstance(chain_argv, list) or not chain_argv or not all(isinstance(item, str) for item in chain_argv):
                raise OwnershipConflict("Existing Codex notify chain is malformed")
            writes.append((chain_path, json.dumps({"argv": chain_argv}, ensure_ascii=False, indent=2) + "\n"))
            touched.append(chain_path)
            notify_cmd += ["--chain-file", _runtime_path(chain_path, platform)]
        elif planner.read(chain_path) is not None:
            chain = load_object(chain_path)
            chain_argv = chain.get("argv")
            if not isinstance(chain_argv, list) or not chain_argv or not all(isinstance(item, str) for item in chain_argv):
                raise ValueError(f"geçersiz Codex notify zinciri: {chain_path}")
            notify_cmd += ["--chain-file", _runtime_path(chain_path, platform)]
        updated_toml = update_codex_config_toml(existing_toml, notify_cmd)
        writes += [(config_toml_path, updated_toml)]
        touched += [config_toml_path]

    if "cursor" in providers:
        config = home / ".cursor"
        hooks_path = config / "hooks.json"
        hooks = load_object(hooks_path)
        hooks.setdefault("version", 1)
        additions = {
            "sessionStart": [{"command": bridge_command(vault, "cursor", "start", platform), "timeout": 15}],
            "beforeSubmitPrompt": [{"command": bridge_command(vault, "cursor", "prompt", platform), "timeout": 5}],
            "sessionEnd": [{"command": bridge_command(vault, "cursor", "end", platform), "timeout": 10}],
            "preCompact": [{"command": bridge_command(vault, "cursor", "precompact", platform), "timeout": 10}],
            "afterAgentResponse": [{"command": bridge_command(vault, "cursor", "turn", platform), "timeout": 10}],
        }
        merge_simple_hooks(hooks, "cursor", additions)
        rule_path = config / "rules" / CURSOR_RULE
        legacy_rule_path = config / "rules" / LEGACY_CURSOR_RULE
        if planner.read(legacy_rule_path) is not None:
            if planner.read(rule_path) is not None:
                raise ValueError("legacy ve current Cursor rule dosyaları çakışıyor")
            legacy_content = planner.text(legacy_rule_path)
            if classify_managed_block(legacy_content) != "legacy":
                raise ValueError("legacy Cursor rule yönetilen dosya olarak doğrulanamadı")
            writes.append((legacy_rule_path, None))
            touched.append(legacy_rule_path)
        cursor_rule = merge_managed(planner.text(rule_path), rule) if planner.read(rule_path) is not None else "---\ndescription: Global second-brain memory\nalwaysApply: true\n---\n\n" + rule + "\n"
        writes += [(hooks_path, json.dumps(hooks, ensure_ascii=False, indent=2) + "\n"), (rule_path, cursor_rule)]
        writes += copy_skills(vault, [config / "skills"])
        touched += [hooks_path, rule_path]

    if "claude" in providers:
        config = home / ".claude"
        settings_path = config / "settings.json"
        settings = load_object(settings_path)
        commands = {
            "SessionStart": (bridge_command(vault, "claude", "start", platform), 15),
            "UserPromptSubmit": (bridge_command(vault, "claude", "prompt", platform), 5),
            "SessionEnd": (bridge_command(vault, "claude", "end", platform), 3),
            "PreCompact": (bridge_command(vault, "claude", "precompact", platform), 10),
            "Stop": (bridge_command(vault, "claude", "turn", platform), 10),
        }
        merge_grouped_hooks(settings, "claude", commands, async_events=frozenset({"Stop"}))
        rule_path = config / "CLAUDE.md"
        writes += [(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n"), (rule_path, merge_managed(planner.text(rule_path), rule))]
        writes += copy_skills(vault, [config / "skills"])
        touched += [settings_path, rule_path]

    return writes, touched



def mcp_destinations(profile):
    home = profile.user_home
    if profile.platform.startswith("windows"):
        appdata = home / "AppData/Roaming"
    elif sys.platform == "darwin":
        appdata = home / "Library/Application Support"
    else:
        appdata = home / ".config"
    paths = [home / ".claude.json", home / ".cursor/mcp.json", home / ".codeium/windsurf/mcp_config.json", appdata / "Claude/claude_desktop_config.json"]
    if (home / ".gemini").is_dir():
        paths.append(home / ".gemini/config/mcp_config.json")
    storage = appdata / "Code/User/globalStorage"
    for extension, filename in [("saoudrizwan.claude-dev", "cline_mcp_settings.json"), ("rooveterinaryinc.roo-cline", "roo_mcp_settings.json")]:
        if (storage / extension).is_dir():
            paths.append(storage / extension / "settings" / filename)
    return tuple(paths)

def plan_integrations(ctx, profile, desired, backend):
    if not any(desired.get(key, False) for key in ("global", "mcp", "schedule", "shortcut")):
        return ()
    validate_profile(ctx, profile)
    planner = _Planner(backend)
    if desired.get("global"):
        writes, _ = _global_writes(ctx, profile, planner)
        for key, content in writes:
            planner.put("file", key, content)
    if desired.get("mcp"):
        argv = launch_argv(ctx, profile, "mcp")
        entry = {"command": argv[0], "args": argv[1:]}
        for path in mcp_destinations(profile):
            document = planner.object(path, "mcp")
            servers = document.setdefault("mcpServers", {})
            if not isinstance(servers, dict):
                raise ValueError(f"Invalid mcpServers: {path}")
            previous = servers.get("respected-vault")
            if previous is not None:
                same_target = isinstance(previous, dict) and previous.get("command") == entry["command"] and previous.get("args") == entry["args"]
                proofs = getattr(backend, "_legacy_proofs", {})
                proven_legacy = isinstance(proofs, dict) and proofs.get(("mcp", str(path))) == planner.read(path, "mcp")
                if not same_target and not proven_legacy:
                    raise OwnershipConflict(f"Unknown respected-vault MCP registration: {path}")
                entry_for_path = dict(previous, **entry) if isinstance(previous, dict) else entry
            else:
                entry_for_path = entry
            servers["respected-vault"] = entry_for_path
            planner.put("mcp", path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    if desired.get("mcp") and (profile.user_home / ".gemini").is_dir():
        from .mcp.server import RespectedMcpServer, _detect_vault_identity
        server = RespectedMcpServer.__new__(RespectedMcpServer)
        server.os_name, server.companion_name = _detect_vault_identity(ctx)
        directory = profile.user_home / ".gemini/antigravity-ide/mcp/respected-vault"
        instructions = f"# Respected Brain MCP Server\n\nBu sunucu, kalıcı ikinci beyin vault'una ({ctx.paths.vault_root.name}) doğrudan erişim sağlar.\nBaşka projelerde çalışırken mimari kararları, kuralları veya geçmiş bilgileri sorgulamak için bu araçları kullan.\n"
        _assert_owned_replacement(ctx, planner, directory / "instructions.md", instructions.encode("utf-8"), kind="mcp")
        planner.put("mcp", directory / "instructions.md", instructions)
        for tool in server.get_tools_manifest():
            path = directory / (tool["name"] + ".json")
            content = json.dumps({"name": tool["name"], "description": tool["description"], "parameters": tool["inputSchema"]}, ensure_ascii=False, indent=2)
            _assert_owned_replacement(ctx, planner, path, content.encode("utf-8"), kind="mcp")
            planner.put("mcp", path, content)
    if desired.get("schedule"):
        from .scheduling.service import plan_schedule
        for row in plan_schedule(ctx, profile, backend):
            planner.put(row.kind, row.key, row.after)
    if desired.get("shortcut"):
        if profile.platform != "windows-native":
            raise FoundationError("Native shortcut registration is unavailable for this profile")
        key = profile.user_home / "Desktop/Respected Brain.lnk"
        argv = launch_argv(ctx, profile, "dashboard")
        previous = planner.read(key, "shortcut")
        if previous is not None:
            document = json.loads(previous)
            proofs = getattr(backend, "_legacy_proofs", {})
            proven_legacy = isinstance(proofs, dict) and proofs.get(("shortcut", str(key))) == previous
            if not proven_legacy and (document.get("target") != argv[0] or document.get("arguments") != subprocess.list2cmdline(argv[1:]) or document.get("description") != "Respected Brain " + ctx.paths.vault_id):
                raise OwnershipConflict("Existing shortcut does not target the selected vault launcher")
        planner.put("shortcut", key, canonical_json({"target": argv[0], "arguments": subprocess.list2cmdline(argv[1:]), "working_directory": str(ctx.paths.app_root), "description": "Respected Brain " + ctx.paths.vault_id, "icon_location": "", "window_style": 1, "hotkey": ""}))
    return planner.changes()


def render_project_integrations(ctx, profile):
    """Fresh-vault hook files; caller owns transactional writes after UUID creation."""
    validate_profile(ctx, profile)
    class EmptyBackend:
        def read(self, kind, key):
            return None
    local_profile = IntegrationProfile(profile.platform, profile.launcher, ctx.paths.vault_root)
    planner = _Planner(EmptyBackend())
    writes, _ = _global_writes(ctx, local_profile, planner)
    mapping = {".claude/settings.json": ".claude/settings.json", ".codex/hooks.json": ".codex/hooks.json", ".cursor/hooks.json": ".cursor/hooks.json", ".gemini/config/hooks.json": ".agents/hooks.json", ".gemini/settings.json": ".gemini/settings.json"}
    result = {}
    def local_commands(value):
        if isinstance(value, dict):
            return {key: item.replace(" --global-hook", "") if key == "command" and isinstance(item, str) else local_commands(item) for key, item in value.items()}
        if isinstance(value, list):
            return [local_commands(item) for item in value]
        return value
    for path, content in writes:
        relative = path.relative_to(ctx.paths.vault_root).as_posix()
        if relative in mapping:
            result[mapping[relative]] = (json.dumps(local_commands(json.loads(content)), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return result
