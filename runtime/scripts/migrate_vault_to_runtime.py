#!/usr/bin/env python3
"""Respected Brain — Vault to Runtime Migration Tool.

Separates engine code from vault data:
1. Deploys runtime into AppData/Local/RespectedBrain (or configured location).
2. Cleans executable code, engine scripts and .state from the target vault.
3. Leaves the vault 100% pure markdown notes and companion memories.
4. Generates fresh self-healing Vault-Map.md and Skills-Map.md.
5. Re-links global AI hooks to the external runtime.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.parent.name == "runtime" else Path(__file__).resolve().parent.parent
RUNTIME_SRC = REPO_ROOT / "runtime"
SCRIPTS_DIR = (REPO_ROOT / "runtime" / "scripts") if (REPO_ROOT / "runtime" / "scripts").is_dir() else (REPO_ROOT / "scripts")

if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime_hub import get_runtime_dir, resolve_vault_path  # noqa: E402
import map_builder  # noqa: E402
import install_global  # noqa: E402


def deploy_runtime(
    target_runtime: Path,
    vault_path: Path,
    companion: str = "Jarvis",
    user_name: str = "Furkan",
) -> None:
    """Copy runtime files into the target runtime directory."""
    print(f"• Runtime kopyalanıyor: {target_runtime}")
    target_runtime.mkdir(parents=True, exist_ok=True)

    # 1. Copy runtime folder
    for item in RUNTIME_SRC.iterdir():
        if item.name in {"__pycache__", ".state", "state"}:
            continue
        dest = target_runtime / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # 2. Copy helper scripts to runtime/scripts
    target_scripts = target_runtime / "scripts"
    target_scripts.mkdir(parents=True, exist_ok=True)
    for s in SCRIPTS_DIR.glob("*.py"):
        shutil.copy2(s, target_scripts / s.name)

    # 3. Create or update config.json in runtime
    config_file = target_runtime / "config.json"
    existing_cfg = {}
    if config_file.is_file():
        try:
            existing_cfg = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read legacy config from vault if present
    legacy_cfg = {}
    vault_cfg = vault_path / ".beyin" / "config.json"
    if vault_cfg.is_file():
        try:
            legacy_cfg = json.loads(vault_cfg.read_text(encoding="utf-8"))
        except Exception:
            pass

    platform_name = "windows-native" if os.name == "nt" else "portable"
    py_cmd = legacy_cfg.get("python_command")
    if not py_cmd or (os.name == "nt" and py_cmd == ["python3"]):
        py_cmd = [sys.executable]

    plat = legacy_cfg.get("platform")
    if not plat or (os.name == "nt" and plat == "portable"):
        plat = platform_name

    merged_cfg = {
        "schema_version": 2,
        "vault_path": str(vault_path.resolve()),
        "user_name": legacy_cfg.get("user_name", user_name),
        "companion_name": legacy_cfg.get("companion", companion),
        "summary_provider": legacy_cfg.get("summary_provider", "auto"),
        "provider_fallback": legacy_cfg.get("provider_fallback", True),
        "platform": plat,
        "environment": legacy_cfg.get("environment", "native"),
        "provider_priority": legacy_cfg.get("provider_priority", [
            "antigravity", "gemini", "codex", "claude", "cursor"
        ]),
        "python_command": py_cmd,
    }
    merged_cfg.update(existing_cfg)
    if os.name == "nt":
        merged_cfg["platform"] = "windows-native"
        if merged_cfg.get("python_command") == ["python3"]:
            merged_cfg["python_command"] = [sys.executable]
    merged_cfg["vault_path"] = str(vault_path.resolve())

    config_file.write_text(json.dumps(merged_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✔ Runtime başarıyla hazırlandı ({config_file})")


def clean_vault(vault_path: Path, target_runtime: Path, companion: str, user_name: str) -> None:
    """Remove engine scripts and code clutter from vault, leaving pure data."""
    print(f"• Kasa temizleniyor: {vault_path}")

    # 1. Write lightweight .respected.json metadata marker
    marker_file = vault_path / ".respected.json"
    marker_data = {
        "schema_version": 2,
        "vault_id": "respected-vault",
        "runtime_dir": str(target_runtime.resolve()),
        "companion": companion,
        "user_name": user_name,
    }
    marker_file.write_text(json.dumps(marker_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 2. Remove technical code directories from vault
    targets_to_remove = [
        vault_path / ".beyin",
        vault_path / "scripts",
        vault_path / "installer",
        vault_path / "__pycache__",
        vault_path / ".state",
        vault_path / ".agents",
        vault_path / ".cursor",
        vault_path / ".claude",
        vault_path / ".codex",
        vault_path / ".gemini",
    ]
    for target in targets_to_remove:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            print(f"  - Temizlendi (klasör): {target.name}")
        elif target.is_file():
            target.unlink(missing_ok=True)
            print(f"  - Temizlendi (dosya): {target.name}")

    # 3. Clean any stray .py files and root AI adapters at vault root
    for py_file in vault_path.glob("*.py"):
        py_file.unlink(missing_ok=True)
        print(f"  - Temizlendi: {py_file.name}")

    for adapter_file in [vault_path / "AGENTS.md", vault_path / "CLAUDE.md", vault_path / "setup.py"]:
        if adapter_file.is_file():
            adapter_file.unlink(missing_ok=True)
            print(f"  - Temizlendi: {adapter_file.name}")

    print("✔ Kasa kod artıklarından tamamen arındırıldı.")


def repair_and_relink(vault_path: Path, target_runtime: Path) -> None:
    """Regenerate maps and re-link global hooks to the external runtime."""
    print("• Self-Healing: Haritalar yenileniyor...")
    map_builder.repair_maps(vault_path, runtime_dir=target_runtime)
    print("✔ Vault-Map.md ve Skills-Map.md güncellendi.")

    print("• Global AI araçları yeni runtime'a bağlanıyor...")
    import subprocess
    platform_name = "windows-native" if os.name == "nt" else "portable"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "install_global.py"),
        str(vault_path),
        "--home",
        str(Path.home()),
        "--platform",
        platform_name,
        "--apply",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        print("✔ Global kancalar ve kurallar başarıyla güncellendi.")
    else:
        print(f"  (Uyarı: Global bağlama sırasında bilgi: {res.stderr or res.stdout})")


def migrate(vault_path: Path, target_runtime: Path | None = None) -> int:
    resolved_vault = vault_path.resolve()
    if not resolved_vault.is_dir():
        print(f"HATA: Kasa dizini bulunamadı: {resolved_vault}", file=sys.stderr)
        return 1

    runtime_dir = target_runtime or get_runtime_dir()
    print("=" * 60)
    print(" Respected Brain 2.0: Motor (Runtime) & Kasa Ayrımı Geçişi")
    print("=" * 60)
    print(f"Kaynak Kasa:    {resolved_vault}")
    print(f"Hedef Runtime:  {runtime_dir}")
    print("-" * 60)

    # Dynamic identity extraction
    cfg: dict[str, str] = {}
    for cand_file in [
        runtime_dir / "config.json",
        resolved_vault / ".beyin" / "config.json",
        resolved_vault / ".respected.json",
    ]:
        if cand_file.is_file():
            try:
                cfg = json.loads(cand_file.read_text(encoding="utf-8"))
                if cfg:
                    break
            except Exception:
                pass
    companion = cfg.get("companion") or cfg.get("companion_name") or "Jarvis"
    user_name = cfg.get("user_name") or "Furkan"

    deploy_runtime(runtime_dir, resolved_vault, companion=companion, user_name=user_name)
    clean_vault(resolved_vault, runtime_dir, companion=companion, user_name=user_name)
    repair_and_relink(resolved_vault, runtime_dir)

    print("=" * 60)
    print("🎉 GEÇİŞ BAŞARIYLA TAMAMLANDI!")
    print(f"Kasanız artık %100 saf Obsidian notlarından oluşuyor: {resolved_vault}")
    print(f"Tüm motor ve arka plan servisleri taşındı:         {runtime_dir}")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=None, help="Target vault path to migrate")
    parser.add_argument("--runtime", "--runtime-dir", dest="runtime_dir", type=Path, default=None, help="Target runtime directory")
    args = parser.parse_args()

    vault_dir = args.vault or resolve_vault_path() or (Path.home() / "Documents" / "RespectedOS")
    return migrate(vault_dir, args.runtime_dir)


if __name__ == "__main__":
    raise SystemExit(main())
