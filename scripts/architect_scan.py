#!/usr/bin/env python3
"""Codebase Architect Scanner - Kod Tabanı Mimari ve Karar Tarayıcısı.

Verilen bir yazılım projesini analiz ederek:
  1. Dilleri ve dosya dağılımını
  2. Modül mimarisini (çekirdek vs yardımcı klasörler)
  3. Giriş noktalarını (entry points)
  4. Bağımlılıkları (dependencies)
  5. Operasyonel sinyalleri (Docker, CI/CD, Makefile)
  6. Git commit karar geçmişini (feat/refactor/arch commitleri)
çıkarır ve kasaya doğrudan işlenebilir AI-First mimari dokümanı üretir.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Bash",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".html": "HTML",
    ".css": "CSS",
}

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", "dist", "build", ".next", ".cache",
    ".claude", ".cursor", ".beyin", ".gemini", "target",
}

ENTRY_POINT_NAMES = {
    "main.py", "app.py", "server.py", "index.ts", "index.js",
    "main.go", "main.rs", "app.ts", "server.ts", "cli.py",
    "manage.py", "application.py", "wsgi.py", "asgi.py",
}


def detect_languages(root: Path) -> Dict[str, int]:
    """Kod tabanındaki dilleri ve dosya sayılarını belirler."""
    counts: Dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for f in filenames:
            ext = Path(f).suffix.lower()
            lang = LANGUAGE_EXTENSIONS.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def detect_modules(root: Path) -> List[Dict[str, Any]]:
    """Üst düzey modülleri ve dizin yapılarını çıkarır."""
    modules: List[Dict[str, Any]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: e.name.lower())
    except OSError:
        return []

    for entry in entries:
        if entry.is_dir() and entry.name not in EXCLUDED_DIRS and not entry.name.startswith("."):
            # Alt dosya sayısını hesapla
            file_count = 0
            for _, _, files in os.walk(entry):
                file_count += len(files)
                if file_count > 500:
                    break
            
            is_core = entry.name.lower() in {"src", "core", "lib", "app", "pkg", "internal", "services", "models", "api"}
            modules.append({
                "name": entry.name,
                "path": entry.name,
                "file_count": file_count,
                "kind": "core" if is_core else "support",
            })
    return modules


def detect_dependencies(root: Path) -> List[str]:
    """Bağımlılık manifestolarından temel kütüphaneleri çıkarır."""
    deps: List[str] = []

    # package.json
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            deps.extend([f"{k} ({v})" for k, v in list(all_deps.items())[:20]])
        except Exception:
            pass

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            matches = re.findall(r'["\']([a-zA-Z0-9_\-\.]+)(?:[><=~^].*?)?["\']', content)
            deps.extend(list(set(matches))[:20])
        except Exception:
            pass

    # requirements.txt
    reqs = root / "requirements.txt"
    if reqs.exists():
        try:
            for line in reqs.read_text(encoding="utf-8").splitlines():
                clean = line.split("#")[0].strip()
                if clean and not clean.startswith("-"):
                    deps.append(clean)
        except Exception:
            pass

    # Cargo.toml
    cargo = root / "Cargo.toml"
    if cargo.exists():
        deps.append("Rust Cargo dependencies")

    # go.mod
    gomod = root / "go.mod"
    if gomod.exists():
        deps.append("Go module dependencies")

    return deps[:30]


def detect_entry_points(root: Path) -> List[str]:
    """Giriş noktalarını tespit eder."""
    points: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for f in filenames:
            if f in ENTRY_POINT_NAMES:
                rel = Path(dirpath, f).relative_to(root).as_posix()
                points.append(rel)
    return sorted(points)


def detect_signals(root: Path) -> Dict[str, bool]:
    """Operasyonel altyapı sinyallerini tespit eder."""
    return {
        "has_docker": (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists(),
        "has_makefile": (root / "Makefile").exists(),
        "has_ci": (root / ".github" / "workflows").is_dir() or (root / ".gitlab-ci.yml").exists(),
        "has_tests": (root / "tests").is_dir() or (root / "test").is_dir(),
    }


def mine_git_decisions(root: Path, limit: int = 15) -> List[Dict[str, str]]:
    """Git commit geçmişindeki mimari ve teknik kararları süzer."""
    if not (root / ".git").is_dir():
        return []

    try:
        res = subprocess.run(
            ["git", "-C", str(root), "log", f"-n{limit * 3}", "--pretty=format:%h|%ad|%s", "--date=short"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if res.returncode != 0:
            return []

        decisions: List[Dict[str, str]] = []
        pattern = re.compile(r"^(feat|refactor|arch|fix|breaking|decision|sec|perf)\s*(?:\(.*?\))?\s*[:：]", re.IGNORECASE)

        for line in res.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                hash_val, date_str, msg = parts
                if pattern.search(msg) or any(w in msg.lower() for w in ["migrate", "upgrade", "remove", "replace", "switch to"]):
                    decisions.append({
                        "commit": hash_val,
                        "date": date_str,
                        "message": msg.strip(),
                    })
                    if len(decisions) >= limit:
                        break
        return decisions
    except Exception:
        return []


def scan_codebase(root: Path) -> Dict[str, Any]:
    """Tüm analiz adımlarını birleştirir."""
    root = root.resolve()
    name = root.name
    langs = detect_languages(root)
    primary_lang = next(iter(langs.keys())) if langs else "Generic"
    modules = detect_modules(root)
    deps = detect_dependencies(root)
    entry_points = detect_entry_points(root)
    signals = detect_signals(root)
    git_decisions = mine_git_decisions(root)

    return {
        "name": name,
        "path": str(root),
        "primary_language": primary_lang,
        "languages": langs,
        "modules": modules,
        "dependencies": deps,
        "entry_points": entry_points,
        "signals": signals,
        "git_decisions": git_decisions,
        "scan_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def to_markdown(data: Dict[str, Any]) -> str:
    """Analiz sonucunu AI-First Markdown formatına döker."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    name = data["name"]

    lines = [
        "---",
        f"title: {name} - Mimari Harita",
        f"created: {today}",
        f"updated: {today}",
        "type: architecture",
        f"project: {name}",
        "freshness: dated",
        "tags: [architecture, project, codebase]",
        "---",
        "",
        "## For future agent",
        f"> **Özet:** {name} projesinin otomatik taranmış mimari yapısı, giriş noktaları, modül hiyerarşisi ve karar geçmişi.",
        f"> **Ana Dil:** {data['primary_language']} | **Taranma Tarihi:** (as of {today})",
        f"> **Kaynak Dizin:** `{data['path']}`",
        "",
        f"# {name} Mimari Notu",
        "",
        "## 1. Diller ve Dağılım",
    ]

    for lang, count in list(data["languages"].items())[:8]:
        lines.append(f"- **{lang}**: {count} dosya")

    lines.append("\n## 2. Modül Hiyerarşisi")
    for mod in data["modules"]:
        kind_tag = "🔴 Çekirdek" if mod["kind"] == "core" else "⚪ Destek"
        lines.append(f"- `/{mod['name']}` ({kind_tag}) - ~{mod['file_count']} dosya")

    lines.append("\n## 3. Giriş Noktaları (Entry Points)")
    if data["entry_points"]:
        for ep in data["entry_points"]:
            lines.append(f"- `{ep}`")
    else:
        lines.append("- Belirgin bir ana giriş noktası tespit edilemedi.")

    lines.append("\n## 4. Altyapı ve Operasyonel Sinyaller")
    sig = data["signals"]
    lines.append(f"- Docker: {'✅ Mevcut' if sig['has_docker'] else '❌ Yok'}")
    lines.append(f"- CI/CD: {'✅ Mevcut' if sig['has_ci'] else '❌ Yok'}")
    lines.append(f"- Makefile: {'✅ Mevcut' if sig['has_makefile'] else '❌ Yok'}")
    lines.append(f"- Test Paketi: {'✅ Mevcut' if sig['has_tests'] else '❌ Yok'}")

    if data["dependencies"]:
        lines.append("\n## 5. Temel Bağımlılıklar")
        for d in data["dependencies"][:15]:
            lines.append(f"- `{d}`")

    if data["git_decisions"]:
        lines.append("\n## 6. Git Karar Geçmişi (Decision Mining)")
        for gd in data["git_decisions"]:
            lines.append(f"- **{gd['date']}** (`{gd['commit']}`): {gd['message']}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Codebase Architect Scanner")
    parser.add_argument("--path", default=".", help="Taranacak kod tabanı dizini")
    parser.add_argument("--json", action="store_true", help="JSON çıktısı ver")
    parser.add_argument("--output", help="Markdown çıktısının kaydedileceği dosya yolu")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"HATA: Geçersiz dizin: {root}", file=sys.stderr)
        return 1

    data = scan_codebase(root)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    md = to_markdown(data)
    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md, encoding="utf-8")
        print(f"Mimari dokümanı kaydedildi: {out_p}")
    else:
        print(md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
