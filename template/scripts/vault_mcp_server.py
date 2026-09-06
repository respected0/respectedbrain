#!/usr/bin/env python3
"""RespectedOS Global MCP Vault Sunucusu (respected-vault-mcp).

Model Context Protocol (MCP) JSON-RPC 2.0 stdio sunucusu.
Kullanıcının başka projelerde çalışırken Antigravity, Claude Code, Codex veya
herhangi bir MCP uyumlu ajandan RespectedOS ikinci beynine doğrudan erişmesini sağlar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from arama import SearchEngine, resolve_vault_root
except ImportError:
    # template içinden çağrılma durumu
    from scripts.arama import SearchEngine, resolve_vault_root


class RespectedMcpServer:
    """RespectedOS Vault MCP stdio Sunucusu."""

    SERVER_NAME = "respected-vault-mcp"
    SERVER_VERSION = "1.0.0"
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()
        self.search_engine = SearchEngine(self.vault_root)

    def _safe_resolve(self, relative_path: str) -> Path | None:
        """Path traversal güvenliği ile vault içindeki dosyayı bulur."""
        clean = Path(relative_path.strip().lstrip("/\\"))
        target = (self.vault_root / clean).resolve()
        try:
            target.relative_to(self.vault_root)
        except ValueError:
            return None
        return target

    def get_tools_manifest(self) -> list[dict[str, Any]]:
        """Sunulan araçların tanımları."""
        return [
            {
                "name": "respected_search",
                "description": (
                    "RespectedOS ikinci beyin vault'undaki notlarda hızlı, anlamsal ve tam metin arama yapar. "
                    "Başka projelerde kod yazarken mimari kararları, hafıza kayıtlarını veya teknik notları bulmak için kullan."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Aranacak anahtar kelime, soru veya konu"},
                        "limit": {"type": "integer", "description": "Döndürülecek maksimum sonuç sayısı (varsayılan: 5)", "default": 5},
                        "category": {"type": "string", "description": "Filtrelenecek klasör/kategori (örn: '🧠 500-Knowledge', '🏰 300-Projects')"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "respected_get_note",
                "description": "Vault içindeki belirli bir markdown notunun tam metnini okur.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Vault köküne göre göreceli not yolu (örn: '🧠 500-Knowledge/Mimari.md')"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "respected_get_decisions",
                "description": "RespectedOS içinde kayıtlı mimari kararları, kuralları ve ADR özetlerini getirir.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "İsteğe bağlı: Belirli bir projenin adı (örn: 'secondbrain')"},
                    },
                    "required": [],
                },
            },
            {
                "name": "respected_get_companion_context",
                "description": "Jarvis / RespectedOS derin hafıza özetini getirir (Core ilkeleri, Kurallar.md, Last-Session ve açık Threads).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "respected_quick_capture",
                "description": "Dış bir projede çalışırken RespectedOS vault'unun Inbox/Dump klasörüne yeni bir not, karar veya fikir bırakır.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Not başlığı"},
                        "content": {"type": "string", "description": "Notun gövde metni"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "İsteğe bağlı etiketler"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "respected_remember",
                "description": (
                    "Dış projede çalışırken öğrenilen kalıcı bir kuralı, teknik kısıtı veya mimari gotcha'yı "
                    "RespectedOS vault'una epistemik sözleşmeyle (scope, confidence, supersedes) atomik olarak kaydeder."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Dersin veya kuralın başlığı"},
                        "content": {"type": "string", "description": "Detaylı açıklama, bağlam veya kod örneği"},
                        "scope": {
                            "type": "string",
                            "enum": ["project", "platform", "general"],
                            "description": "Kapsam: 'project' (yalnızca bu proje), 'platform' (örn: ios, react, flutter), 'general' (evrensel kural)",
                            "default": "general",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["verified", "inferred", "unverified"],
                            "description": "Güvenilirlik: 'verified' (kodla test edildi), 'inferred' (çıkarım), 'unverified' (şüpheli)",
                            "default": "verified",
                        },
                        "supersedes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "İsteğe bağlı: Bu kuralın geçersiz kıldığı eski kural veya not isimleri",
                        },
                        "project": {"type": "string", "description": "İsteğe bağlı proje adı (scope: project ise zorunlu)"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "İsteğe bağlı etiketler"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "respected_expand",
                "description": (
                    "Belirli bir notun komşuluk grafiğini getirir: Notun içinden dışarıya verilen bağlantılar (outbound links) "
                    "ve kasadaki diğer notlardan bu nota verilen geri bağlantılar (backlinks)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title_or_path": {"type": "string", "description": "İncelenecek notun başlığı veya dosya yolu (örn: 'React Gotchas' veya '🧠 500-Knowledge/React.md')"},
                    },
                    "required": ["title_or_path"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """İlgili aracı çalıştırıp metin yanıtı döndürür."""
        if name == "respected_search":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 5))
            category = arguments.get("category")
            results = self.search_engine.search(query, limit=limit, category=category)
            if not results:
                return f"'{query}' sorgusu için RespectedOS içinde eşleşen not bulunamadı."
            
            lines = [f"### RespectedOS Arama Sonuçları: '{query}' ({len(results)} sonuç)\n"]
            for r in results:
                lines.append(f"- **[{r['title']}]({r['path']})** (Kategori: `{r['category']}`, Skor: {r['score']})")
                if r.get("snippet"):
                    lines.append(f"  > {r['snippet']}\n")
            return "\n".join(lines)

        elif name == "respected_get_note":
            rel_path = arguments.get("path", "")
            target = self._safe_resolve(rel_path)
            if not target or not target.is_file():
                return f"Hata: '{rel_path}' dosyası RespectedOS vault'u içinde bulunamadı."
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                return f"### Dosya: {rel_path}\n\n{content}"
            except Exception as e:
                return f"Dosya okunurken hata oluştu: {e}"

        elif name == "respected_get_decisions":
            project = arguments.get("project")
            # 1. 500-Knowledge, Projects ve Companion altındaki karar ve kuralları ara
            search_query = f"{project} karar" if project else "karar mimari kural ADR"
            results = self.search_engine.search(search_query, limit=8)
            kurallar_file = self.vault_root / "🔮 850-Companion" / "Kurallar.md"
            kurallar_text = ""
            if kurallar_file.is_file():
                kurallar_text = f"\n\n### Aktif Kurallar (Kurallar.md):\n{kurallar_file.read_text(encoding='utf-8', errors='replace')[:2000]}"

            lines = ["### RespectedOS Karar ve Mimari Kayıtları:\n"]
            for r in results:
                lines.append(f"- **{r['title']}** (`{r['path']}`): {r['snippet']}")
            lines.append(kurallar_text)
            return "\n".join(lines)

        elif name == "respected_get_companion_context":
            companion_dir = self.vault_root / "🔮 850-Companion"
            files_to_read = [
                ("Core", companion_dir / "Core.md"),
                ("Last-Session", companion_dir / "Last-Session.md"),
                ("Kurallar", companion_dir / "Kurallar.md"),
                ("Threads", companion_dir / "Threads.md"),
            ]
            parts = ["## RespectedOS Jarvis Companion Hafıza Özeti\n"]
            for label, fpath in files_to_read:
                if fpath.is_file():
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    parts.append(f"### {label}\n{content.strip()}\n")
                else:
                    parts.append(f"### {label}\n(Mevcut değil)\n")
            return "\n".join(parts)

        elif name == "respected_quick_capture":
            title = arguments.get("title", "Hızlı Not").strip()
            content = arguments.get("content", "").strip()
            tags = arguments.get("tags", [])

            safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title)[:40]
            now = dt.datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{safe_slug}.md"

            inbox_dump = self.vault_root / "📥 000-Inbox" / "Dump"
            inbox_dump.mkdir(parents=True, exist_ok=True)
            target_file = inbox_dump / filename

            tag_list_str = ", ".join(f'"{t}"' for t in tags) if tags else ""
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")

            note_body = (
                f"---\n"
                f'title: "{title}"\n'
                f'created: "{date_str}"\n'
                f'type: capture\n'
                f'status: inbox\n'
                f"tags: [{tag_list_str}]\n"
                f"source: mcp_external\n"
                f"---\n\n"
                f"# {title}\n\n"
                f"{content}\n"
            )

            try:
                target_file.write_text(note_body, encoding="utf-8")
                # İndeksi güncelle
                self.search_engine.index_vault()
                return f"Başarılı: Not '{filename}' olarak '📥 000-Inbox/Dump/' dizinine kaydedildi ve arama indeksine eklendi."
            except Exception as e:
                return f"Not yazılırken hata oluştu: {e}"

        elif name == "respected_remember":
            title = arguments.get("title", "Kalıcı Ders").strip()
            content = arguments.get("content", "").strip()
            scope = arguments.get("scope", "general")
            confidence = arguments.get("confidence", "verified")
            supersedes = arguments.get("supersedes", [])
            project = arguments.get("project", "").strip()
            tags = arguments.get("tags", [])

            safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title)[:50]
            now = dt.datetime.now()
            timestamp = now.strftime("%Y%m%d")
            filename = f"{timestamp}_{safe_slug}.md"

            if scope == "project" and project:
                dest_dir = self.vault_root / "🏰 300-Projects" / project
            else:
                dest_dir = self.vault_root / "🧠 500-Knowledge"

            dest_dir.mkdir(parents=True, exist_ok=True)
            target_file = dest_dir / filename

            tag_list_str = ", ".join(f'"{t}"' for t in tags) if tags else ""
            sup_list_str = ", ".join(f'"{s}"' for s in supersedes) if supersedes else ""
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")

            note_body = (
                f"---\n"
                f'title: "{title}"\n'
                f'created: "{date_str}"\n'
                f'modified: "{date_str}"\n'
                f'type: lesson\n'
                f'scope: {scope}\n'
                f'confidence: {confidence}\n'
                f'supersedes: [{sup_list_str}]\n'
                f'project: "{project}"\n'
                f'tags: [{tag_list_str}]\n'
                f"source: mcp_remember\n"
                f"---\n\n"
                f"# {title}\n\n"
                f"{content}\n"
            )

            try:
                target_file.write_text(note_body, encoding="utf-8")
                self.search_engine.index_vault()
                rel_path = target_file.relative_to(self.vault_root)
                return (
                    f"Başarılı: Ders '{title}' epistemik sözleşmeyle kaydedildi.\n"
                    f"- Yol: `{rel_path}`\n"
                    f"- Kapsam: `{scope}` | Güvenilirlik: `{confidence}`\n"
                    f"- Geçersiz kıldığı: `{supersedes if supersedes else 'Yok'}`"
                )
            except Exception as e:
                return f"Ders kaydedilirken hata oluştu: {e}"

        elif name == "respected_expand":
            target_str = arguments.get("title_or_path", "").strip()
            target_path = self._safe_resolve(target_str)
            if not target_path or not target_path.is_file():
                found = None
                target_stem = Path(target_str).stem.lower()
                for p in self.vault_root.rglob("*.md"):
                    if p.stem.lower() == target_stem:
                        found = p
                        break
                if not found:
                    return f"'{target_str}' ile eşleşen bir not RespectedOS içinde bulunamadı."
                target_path = found

            rel_target = target_path.relative_to(self.vault_root)
            target_name = target_path.stem

            try:
                content = target_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                return f"Not okunurken hata oluştu: {e}"

            outbound_raw = re.findall(r"\[\[(.*?)\]\]", content)
            outbound = []
            for link in outbound_raw:
                clean_link = link.split("|")[0].split("#")[0].strip()
                if clean_link and clean_link not in outbound:
                    outbound.append(clean_link)

            backlinks = []
            pattern = re.compile(rf"\[\[{re.escape(target_name)}(\|.*?)?(#.*?)?\]\]", re.IGNORECASE)
            for md_file in self.vault_root.rglob("*.md"):
                if md_file.resolve() == target_path.resolve():
                    continue
                try:
                    f_content = md_file.read_text(encoding="utf-8", errors="replace")
                    if pattern.search(f_content):
                        rel_back = md_file.relative_to(self.vault_root)
                        backlinks.append(str(rel_back))
                except Exception:
                    continue

            lines = [
                f"### RespectedOS Grafik Komşuluğu: `{rel_target}`\n",
                f"**📤 Dış Bağlantılar (Bu nottan gidenler - {len(outbound)}):**",
            ]
            if outbound:
                for out in outbound:
                    lines.append(f"- `[[{out}]]`")
            else:
                lines.append("- (Dış bağlantı bulunamadı)")

            lines.append(f"\n**📥 Geri Bağlantılar (Bu nota gelenler - {len(backlinks)}):**")
            if backlinks:
                for back in backlinks:
                    lines.append(f"- `[[{back}]]`")
            else:
                lines.append("- (Geri bağlantı bulunamadı)")

            return "\n".join(lines)

        else:
            return f"Bilinmeyen araç çağrısı: {name}"

    def run_stdio(self) -> None:
        """JSON-RPC 2.0 stdio protokol döngüsü."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": self.PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": self.SERVER_NAME,
                            "version": self.SERVER_VERSION,
                        },
                    },
                }
                self._send(resp)

            elif method == "notifications/initialized":
                # Bildirim, yanıt gerektirmez
                pass

            elif method == "ping":
                self._send({"jsonrpc": "2.0", "id": req_id, "result": {}})

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": self.get_tools_manifest(),
                    },
                }
                self._send(resp)

            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                tool_output = self.call_tool(tool_name, args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": tool_output,
                            }
                        ]
                    },
                }
                self._send(resp)

            else:
                if req_id is not None:
                    self._send({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found",
                        },
                    })

    def _send(self, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False)
        sys.stdout.write(body + "\n")
        sys.stdout.flush()


def register_mcp(vault_root: Path) -> list[str]:
    """Antigravity IDE ve Claude Code için MCP sunucusunu otomatik kaydeder."""
    actions = []
    # 1. Antigravity IDE
    antigravity_mcp_dir = Path.home() / ".gemini" / "antigravity-ide" / "mcp" / "respected-vault"
    if antigravity_mcp_dir.parent.is_dir():
        antigravity_mcp_dir.mkdir(parents=True, exist_ok=True)
        instructions_file = antigravity_mcp_dir / "instructions.md"
        instructions_file.write_text(
            "# Respected Brain MCP Server\n\n"
            f"Bu sunucu, kalıcı ikinci beyin vault'una ({vault_root.name}) doğrudan erişim sağlar.\n"
            "Başka projelerde çalışırken mimari kararları, kuralları veya geçmiş bilgileri sorgulamak için bu araçları kullan.\n",
            encoding="utf-8",
        )
        server = RespectedMcpServer(vault_root)
        for tool in server.get_tools_manifest():
            schema_file = antigravity_mcp_dir / f"{tool['name']}.json"
            schema_data = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"],
            }
            schema_file.write_text(json.dumps(schema_data, indent=2, ensure_ascii=False), encoding="utf-8")
        actions.append(f"Antigravity IDE MCP kayıt edildi: {antigravity_mcp_dir}")

    # 2. Claude Code global config (~/.claude.json)
    claude_json_path = Path.home() / ".claude.json"
    claude_cfg: dict[str, Any] = {}
    if claude_json_path.is_file():
        try:
            claude_cfg = json.loads(claude_json_path.read_text(encoding="utf-8"))
        except Exception:
            claude_cfg = {}
    servers = claude_cfg.setdefault("mcpServers", {})
    server_script = vault_root / "scripts" / "vault_mcp_server.py"
    if not server_script.is_file():
        server_script = SCRIPT_DIR / "vault_mcp_server.py"

    servers["respected-vault"] = {
        "command": sys.executable,
        "args": [str(server_script.resolve()), "--vault", str(vault_root.resolve())],
    }
    try:
        claude_json_path.write_text(json.dumps(claude_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        actions.append(f"Claude Code global MCP kayıt edildi: {claude_json_path}")
    except Exception as e:
        actions.append(f"Claude Code kayıt uyarısı: {e}")

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="RespectedOS Global MCP Vault Sunucusu")
    parser.add_argument("--vault", type=Path, default=None, help="Vault kök dizini")
    parser.add_argument("--test", action="store_true", help="Protokol yerine araçları test et")
    parser.add_argument("--register", action="store_true", help="Antigravity ve Claude Code ortamına MCP sunucusunu kaydet")

    args = parser.parse_args()
    vault = resolve_vault_root(args.vault)
    server = RespectedMcpServer(vault)

    if args.register:
        print(f"RespectedOS Vault: {vault}")
        actions = register_mcp(vault)
        for a in actions:
            print(f"✓ {a}")
        print("\nKayıt tamamlandı. Artık başka projelerde çalışırken 'respected-vault' MCP araçlarını kullanabilirsiniz.")
        return 0

    if args.test:
        print(f"RespectedOS Vault: {vault}")
        print("Mevcut Araçlar:")
        for t in server.get_tools_manifest():
            print(f" - {t['name']}: {t['description']}")
        print("\nTest araması yapılıyor ('hafıza')...")
        print(server.call_tool("respected_search", {"query": "hafıza", "limit": 2}))
        return 0

    server.run_stdio()
    return 0


if __name__ == "__main__":
    sys.exit(main())
