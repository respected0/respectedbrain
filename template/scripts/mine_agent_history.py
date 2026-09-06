#!/usr/bin/env python3
"""Çapraz Ajan Geçmiş Sohbet Madencisi - RespectedOS.

Yerel diskteki Claude Code, Google Antigravity ve OpenAI Codex oturum kayıtlarını
(JSONL) tarayarak ikinci beyin vault'una (daily/ veya inbox/dump) aktarır.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from arama import resolve_vault_root
except ImportError:
    from scripts.arama import resolve_vault_root


class AgentHistoryMiner:
    """Yerel yapay zeka ajanlarının oturum geçmişlerini tarayan ve çıkaran motor."""

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()
        self.state_file = self.vault_root / ".beyin" / "cache" / "imported_sessions.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.imported_ids = self._load_state()

    def _load_state(self) -> set[str]:
        if self.state_file.is_file():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return set(data.get("imported_ids", []))
            except Exception:
                return set()
        return set()

    def _save_state(self) -> None:
        try:
            data = {"imported_ids": sorted(list(self.imported_ids))}
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def discover_antigravity_sessions(self) -> list[dict[str, Any]]:
        """Google Antigravity transcript.jsonl dosyalarını bulur."""
        sessions: list[dict[str, Any]] = []
        user_home = Path.home()
        antigravity_brain = user_home / ".gemini" / "antigravity-ide" / "brain"

        if not antigravity_brain.is_dir():
            return sessions

        pattern = str(antigravity_brain / "*" / ".system_generated" / "logs" / "transcript.jsonl")
        for file_path in glob.glob(pattern):
            p = Path(file_path)
            conv_id = p.parents[2].name
            try:
                stat = p.stat()
                mtime = dt.datetime.fromtimestamp(stat.st_mtime)
                sessions.append({
                    "agent": "antigravity",
                    "id": f"antigravity_{conv_id}",
                    "path": p,
                    "mtime": mtime,
                })
            except OSError:
                continue

        return sessions

    def discover_claude_sessions(self) -> list[dict[str, Any]]:
        """Claude Code geçmiş oturumlarını bulur."""
        sessions: list[dict[str, Any]] = []
        user_home = Path.home()
        claude_dir = user_home / ".claude"

        if not claude_dir.is_dir():
            return sessions

        for p in claude_dir.rglob("*.jsonl"):
            if "session" in p.name.lower() or "transcript" in p.name.lower() or len(p.stem) == 36:
                try:
                    stat = p.stat()
                    mtime = dt.datetime.fromtimestamp(stat.st_mtime)
                    sessions.append({
                        "agent": "claude",
                        "id": f"claude_{p.stem}",
                        "path": p,
                        "mtime": mtime,
                    })
                except OSError:
                    continue

        return sessions

    def discover_codex_sessions(self) -> list[dict[str, Any]]:
        """OpenAI Codex geçmiş oturumlarını bulur."""
        sessions: list[dict[str, Any]] = []
        user_home = Path.home()
        codex_dir = user_home / ".codex" / "sessions"

        if not codex_dir.is_dir():
            return sessions

        for p in codex_dir.glob("*.jsonl"):
            try:
                stat = p.stat()
                mtime = dt.datetime.fromtimestamp(stat.st_mtime)
                sessions.append({
                    "agent": "codex",
                    "id": f"codex_{p.stem}",
                    "path": p,
                    "mtime": mtime,
                })
            except OSError:
                continue

        return sessions

    def parse_session(self, session_info: dict[str, Any]) -> dict[str, Any] | None:
        """JSONL dosyasını okuyup kullanıcı mesajlarını ve önemli kararları imbikten geçirir."""
        file_path: Path = session_info["path"]
        agent = session_info["agent"]
        user_inputs: list[str] = []
        model_thoughts_or_summaries: list[str] = []

        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if agent == "antigravity":
                        msg_type = record.get("type", "")
                        content = str(record.get("content", "")).strip()
                        if msg_type == "USER_INPUT" and content:
                            user_inputs.append(content)
                        elif msg_type == "PLANNER_RESPONSE" and content:
                            if len(content) > 30 and not content.startswith("{"):
                                model_thoughts_or_summaries.append(content[:300].strip())

                    else:
                        role = record.get("role") or record.get("source") or ""
                        content = str(record.get("content") or record.get("text") or record.get("message") or "").strip()
                        if role in ("user", "USER_EXPLICIT") and content:
                            user_inputs.append(content)
                        elif role in ("assistant", "MODEL") and content:
                            if len(content) > 30:
                                model_thoughts_or_summaries.append(content[:300].strip())

        except Exception:
            return None

        if not user_inputs:
            return None

        title = user_inputs[0][:100].replace("\n", " ").strip()
        # XML taglerini ve özel karakterleri temizle
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"[#*`_\[\]]", "", title).strip() or "İsimsiz Oturum"
        title = title[:60].strip()

        return {
            "id": session_info["id"],
            "agent": agent,
            "title": title,
            "mtime": session_info["mtime"],
            "user_inputs": user_inputs,
            "summaries": model_thoughts_or_summaries[:5],
        }

    def import_session(self, parsed: dict[str, Any], target_folder: str = "daily") -> Path:
        """Ayrıştırılan oturumu vault içine markdown dosyası olarak yazar."""
        date_str = parsed["mtime"].strftime("%Y-%m-%d")
        time_str = parsed["mtime"].strftime("%H:%M:%S")

        safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in parsed["title"])[:35]
        filename = f"{date_str}_{parsed['agent']}_{safe_slug}.md"

        if target_folder == "inbox":
            out_dir = self.vault_root / "📥 000-Inbox" / "Dump"
        else:
            out_dir = self.vault_root / "daily"

        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / filename

        inputs_rendered = "\n".join(f"- {u[:200]}" for u in parsed["user_inputs"][:10])
        summaries_rendered = "\n\n".join(f"> {s}..." for s in parsed["summaries"])

        content = (
            f"---\n"
            f'title: "{parsed["title"]}"\n'
            f'created: "{date_str} {time_str}"\n'
            f'valid_at: "{date_str}"\n'
            f'recorded_at: "{dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"\n'
            f'type: session-history\n'
            f'status: imported\n'
            f'agent: "{parsed["agent"]}"\n'
            f'session_id: "{parsed["id"]}"\n'
            f'freshness: dated\n'
            f'tags: ["gecmis-import", "{parsed["agent"]}"]\n'
            f"---\n\n"
            f"# {parsed['title']}\n\n"
            f"**Kaynak Ajan:** `{parsed['agent']}`  \n"
            f"**Tarih:** `{date_str} {time_str}`  \n"
            f"**Oturum Kimliği:** `{parsed['id']}`\n\n"
            f"## Kullanıcı İstekleri / Sorulan Konular\n\n"
            f"{inputs_rendered}\n\n"
            f"## Önemli Çıktılar ve Kararlar\n\n"
            f"{summaries_rendered}\n"
        )

        out_file.write_text(content, encoding="utf-8")
        self.imported_ids.add(parsed["id"])
        self._save_state()
        return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Çapraz Ajan Geçmiş Madencisi")
    parser.add_argument("--source", choices=["all", "claude", "antigravity", "codex"], default="all", help="Taranacak ajan")
    parser.add_argument("--vault", type=Path, default=None, help="Vault kök dizini")
    parser.add_argument("--limit", type=int, default=10, help="Maksimum işlenecek oturum")
    parser.add_argument("--target", choices=["daily", "inbox"], default="daily", help="Hedef klasör")
    parser.add_argument("--dry-run", action="store_true", help="Yazmadan listele")
    parser.add_argument("--force", action="store_true", help="Daha önce aktarılmış olanları tekrar aktar")

    args = parser.parse_args()
    vault = resolve_vault_root(args.vault)
    miner = AgentHistoryMiner(vault)

    candidates: list[dict[str, Any]] = []
    if args.source in ("all", "antigravity"):
        candidates.extend(miner.discover_antigravity_sessions())
    if args.source in ("all", "claude"):
        candidates.extend(miner.discover_claude_sessions())
    if args.source in ("all", "codex"):
        candidates.extend(miner.discover_codex_sessions())

    candidates.sort(key=lambda x: x["mtime"], reverse=True)

    print(f"Toplam {len(candidates)} ajan oturum dosyası bulundu.")

    imported_count = 0
    skipped_count = 0

    for c in candidates:
        if imported_count >= args.limit:
            break

        if not args.force and c["id"] in miner.imported_ids:
            skipped_count += 1
            continue

        parsed = miner.parse_session(c)
        if not parsed:
            continue

        if args.dry_run:
            print(f"[Önizleme] {parsed['agent'].upper()} | {parsed['mtime'].strftime('%Y-%m-%d')} | {parsed['title']}")
            imported_count += 1
        else:
            written_file = miner.import_session(parsed, target_folder=args.target)
            print(f"[Aktarıldı] {written_file.name} ({parsed['agent']})")
            imported_count += 1

    if args.dry_run:
        print(f"\nÖnizleme bitti: {imported_count} oturum aktarılmaya uygun, {skipped_count} zaten aktarılmış.")
    else:
        print(f"\nİşlem tamamlandı: {imported_count} oturum vault'a aktarıldı, {skipped_count} atlandı.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
