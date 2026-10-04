"""Package-owned MCP server; stdout contains JSONRPC only."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from respectedbrain import __version__
from respectedbrain.core.coordination import guarded_writer
from respectedbrain.search.engine import SearchEngine

def _detect_vault_identity(ctx):
    from ..global_config import identity_settings
    settings = identity_settings(ctx)
    return str(settings["OS_NAME"]), str(settings["COMPANION"])


class RespectedMcpServer:
    """Respected Brain Vault MCP stdio Sunucusu."""

    SERVER_NAME = "respected-vault-mcp"
    SERVER_VERSION = __version__
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.vault_root = ctx.paths.vault_root
        self.os_name, self.companion_name = _detect_vault_identity(ctx)
        self.search_engine = SearchEngine(ctx)

    MAX_NOTE_BYTES = 5 * 1024 * 1024  # 5 MB güvenlik tavanı

    def _safe_resolve(self, relative_path: str) -> Path | None:
        """Path traversal, ADS ve NUL byte korumasıyla vault içindeki dosyayı bulur."""
        if not relative_path or not isinstance(relative_path, str):
            return None
        if "\x00" in relative_path or ":" in relative_path:
            return None
        try:
            raw_path = Path(relative_path.strip().lstrip("/\\"))
            # Windows reserved device names
            for part in raw_path.parts:
                stem = part.split(".")[0].upper()
                if stem in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"}:
                    return None
            target = (self.vault_root / raw_path).resolve()
            target.relative_to(self.vault_root)
            return target
        except (ValueError, OSError):
            return None

    def get_tools_manifest(self) -> list[dict[str, Any]]:
        """Sunulan araçların tanımları."""
        return [
            {
                "name": "respected_search",
                "description": (
                    "Kalıcı ikinci beyin vault'undaki notlarda hızlı, anlamsal ve tam metin arama yapar. "
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
                "description": "Kasa içinde kayıtlı mimari kararları, kuralları ve ADR özetlerini getirir.",
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
                "description": f"{self.companion_name} / {self.os_name} derin hafıza özetini getirir (Core ilkeleri, Kurallar.md, Last-Session ve açık Threads).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "respected_quick_capture",
                "description": "Dış bir projede çalışırken ikinci beyin vault'unun Inbox/Dump klasörüne yeni bir not, karar veya fikir bırakır.",
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
                    "ikinci beyin vault'una epistemik sözleşmeyle (scope, confidence, supersedes) atomik olarak kaydeder."
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

    @guarded_writer(busy_result=None)
    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """İlgili aracı çalıştırıp metin yanıtı döndürür."""
        if name == "respected_search":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 5))
            category = arguments.get("category")
            results = self.search_engine.search(query, limit=limit, category=category)
            if not results:
                return f"'{query}' sorgusu için {self.os_name} içinde eşleşen not bulunamadı."

            lines = [f"### {self.os_name} Arama Sonuçları: '{query}' ({len(results)} sonuç)\n"]
            for r in results:
                lines.append(f"- **[{r['title']}]({r['path']})** (Kategori: `{r['category']}`, Skor: {r['score']})")
                if r.get("snippet"):
                    lines.append(f"  > {r['snippet']}\n")
            return "\n".join(lines)

        elif name == "respected_get_note":
            rel_path = arguments.get("path", "")
            target = self._safe_resolve(rel_path)
            if not target or not target.is_file():
                return f"Hata: '{rel_path}' dosyası {self.os_name} vault'u içinde bulunamadı."
            try:
                if target.stat().st_size > self.MAX_NOTE_BYTES:
                    return f"Hata: '{rel_path}' çok büyük ({target.stat().st_size} bayt). Güvenlik sınırı: {self.MAX_NOTE_BYTES} bayt."
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

            lines = [f"### {self.os_name} Karar ve Mimari Kayıtları:\n"]
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
            parts = [f"## {self.os_name} — {self.companion_name} Derin Hafıza Özeti\n"]
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

            safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title)[:40].strip("._-") or "note"
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

            safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title)[:50].strip("._-") or "lesson"
            now = dt.datetime.now()
            timestamp = now.strftime("%Y%m%d")
            filename = f"{timestamp}_{safe_slug}.md"

            if scope == "project" and project:
                clean_project = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project).strip("._-")
                if not clean_project:
                    return "Hata: Geçersiz proje adı."
                dest_dir = (self.vault_root / "🏰 300-Projects" / clean_project).resolve()
                try:
                    dest_dir.relative_to(self.vault_root)
                except ValueError:
                    return "Hata: Proje hedefi vault dışında olamaz."
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
                    return f"'{target_str}' ile eşleşen bir not {self.os_name} içinde bulunamadı."
                target_path = found

            rel_target = target_path.relative_to(self.vault_root)
            target_name = target_path.stem

            try:
                content = target_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                return f"Not okunurken hata oluştu: {e}"

            outbound = []
            outbound_raw = re.findall(r"\[\[(.*?)\]\]", content)
            for link in outbound_raw:
                clean_link = link.split("|")[0].split("#")[0].strip()
                if clean_link and clean_link not in outbound:
                    outbound.append(clean_link)

            # SQLite FTS5 tabanlı anında backlink sorgusu (sıfır disk taraması)
            raw_backlinks = self.search_engine.get_backlinks(target_name)
            if not raw_backlinks:
                self.search_engine.index_vault()
                raw_backlinks = self.search_engine.get_backlinks(target_name)
            backlinks = [b for b in raw_backlinks if Path(b).as_posix() != rel_target.as_posix()]

            lines = [
                f"### {self.os_name} Grafik Komşuluğu: `{rel_target}`\n",
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


def serve(ctx):
    RespectedMcpServer(ctx).run_stdio()
    return 0
