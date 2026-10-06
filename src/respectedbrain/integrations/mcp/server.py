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
from respectedbrain.core.platform import path_within_vault
from respectedbrain.core.coordination import guarded_writer
from respectedbrain.search.engine import SearchEngine
from ..notes import MAX_NOTE_BYTES, create_note, note_path, read_note

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

    MAX_NOTE_BYTES = MAX_NOTE_BYTES

    def _safe_resolve(self, relative_path: str) -> Path | None:
        return note_path(self.vault_root, relative_path)

    def _read_optional(self, relative: str, max_chars: int | None = None) -> str:
        try:
            return read_note(self.vault_root, relative, max_chars=max_chars)
        except (OSError, ValueError):
            return ''

    def _save_note(self, directory: Path, filename: str, body: str) -> tuple[Path, bool]:
        target = create_note(self.vault_root, directory, filename, body)
        try:
            self.search_engine.index_vault()
            indexed = True
        except Exception:
            indexed = False
        return target, indexed

    def _validate_arguments(self, name, arguments) -> None:
        if not isinstance(arguments, dict):
            raise ValueError('arguments must be an object')
        manifest = next((tool for tool in self.get_tools_manifest() if tool['name'] == name), None)
        if manifest is None:
            return
        schema = manifest['inputSchema']
        for required in schema.get('required', []):
            if required not in arguments:
                raise ValueError('missing argument: ' + required)
        for key, value in arguments.items():
            specification = schema['properties'].get(key)
            if specification is None:
                continue
            kind = specification['type']
            valid = ((kind == 'string' and isinstance(value, str)) or
                     (kind == 'integer' and type(value) is int) or
                     (kind == 'array' and isinstance(value, list) and all(isinstance(v, str) for v in value)))
            if not valid or ('enum' in specification and value not in specification['enum']):
                raise ValueError('invalid argument: ' + key)
        if name in {'respected_quick_capture', 'respected_remember'}:
            if not arguments.get('title', '').strip() or not arguments.get('content', '').strip():
                raise ValueError('title and content cannot be empty')
            if arguments.get('scope') == 'project' and not arguments.get('project', '').strip():
                raise ValueError('project is required for project scope')

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
        try:
            self._validate_arguments(name, arguments)
        except ValueError as error:
            return f'Hata: {error}'
        if name == "respected_search":
            query = arguments.get("query", "")
            limit = max(0, min(100, arguments.get("limit", 5)))
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
                content = read_note(self.vault_root, rel_path)
                return f"### Dosya: {rel_path}\n\n{content}"
            except Exception as e:
                return f"Dosya okunurken hata oluştu: {e}"

        elif name == "respected_get_decisions":
            project = arguments.get("project")
            # 1. 500-Knowledge, Projects ve Companion altındaki karar ve kuralları ara
            search_query = f"{project} karar" if project else "karar mimari kural ADR"
            results = self.search_engine.search(search_query, limit=8)
            kurallar_text = ""
            rules = self._read_optional('🔮 850-Companion/Kurallar.md', 2000)
            if rules:
                kurallar_text = f"\n\n### Aktif Kurallar (Kurallar.md):\n{rules}"

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
                content = self._read_optional(fpath.relative_to(self.vault_root).as_posix())
                if content:
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

            tag_list_str = ", ".join(json.dumps(t, ensure_ascii=False) for t in tags)
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")

            note_body = (
                f"---\n"
                f'title: {json.dumps(title, ensure_ascii=False)}\n'
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
                target_file, indexed = self._save_note(inbox_dump, filename, note_body)
                suffix = 'arama indeksine eklendi.' if indexed else 'arama indeksi güncellenemedi; yeniden indeksleyin.'
                return f"Başarılı: Not '{target_file.name}' olarak '📥 000-Inbox/Dump/' dizinine kaydedildi; {suffix}"
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
                dest_dir = self.vault_root / "🏰 300-Projects" / clean_project
                try:
                    dest_dir.relative_to(self.vault_root)
                except ValueError:
                    return "Hata: Proje hedefi vault dışında olamaz."
            else:
                dest_dir = self.vault_root / "🧠 500-Knowledge"


            tag_list_str = ", ".join(json.dumps(t, ensure_ascii=False) for t in tags)
            sup_list_str = ", ".join(json.dumps(s, ensure_ascii=False) for s in supersedes)
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")

            note_body = (
                f"---\n"
                f'title: {json.dumps(title, ensure_ascii=False)}\n'
                f'created: "{date_str}"\n'
                f'modified: "{date_str}"\n'
                f'type: lesson\n'
                f'scope: {scope}\n'
                f'confidence: {confidence}\n'
                f'supersedes: [{sup_list_str}]\n'
                f'project: {json.dumps(project, ensure_ascii=False)}\n'
                f'tags: [{tag_list_str}]\n'
                f"source: mcp_remember\n"
                f"---\n\n"
                f"# {title}\n\n"
                f"{content}\n"
            )

            try:
                target_file, indexed = self._save_note(dest_dir, filename, note_body)
                rel_path = target_file.relative_to(self.vault_root)
                return (
                    f"Başarılı: Ders '{title}' epistemik sözleşmeyle kaydedildi.\n"
                    f"- Yol: `{rel_path}`\n"
                    f"- Kapsam: `{scope}` | Güvenilirlik: `{confidence}`\n"
                    f"- Geçersiz kıldığı: `{supersedes if supersedes else 'Yok'}`\n"
                    + ('Arama indeksine eklendi.' if indexed else 'Arama indeksi güncellenemedi; yeniden indeksleyin.')
                )
            except Exception as e:
                return f"Ders kaydedilirken hata oluştu: {e}"

        elif name == "respected_expand":
            target_str = arguments.get("title_or_path", "").strip()
            target_path = self._safe_resolve(target_str)
            if not target_path or not target_path.is_file():
                if '/' in target_str or '\\' in target_str or ':' in target_str or '\0' in target_str:
                    return 'Hata: Geçersiz veya bulunamayan not yolu.'
                found = []
                target_stem = Path(target_str).stem.lower()
                for root, dirs, files in os.walk(self.vault_root):
                    dirs[:] = [d for d in dirs if path_within_vault(Path(root) / d, self.vault_root)]
                    for filename in files:
                        p = Path(root) / filename
                        if p.suffix == '.md' and p.stem.lower() == target_stem and self._safe_resolve(p.relative_to(self.vault_root).as_posix()):
                            found.append(p)
                if not found:
                    return f"'{target_str}' ile eşleşen bir not {self.os_name} içinde bulunamadı."
                if len(found) > 1:
                    return 'Hata: Birden fazla not eşleşti; göreceli dosya yolunu belirtin.'
                target_path = found[0]

            rel_target = target_path.relative_to(self.vault_root)

            try:
                content = read_note(self.vault_root, rel_target.as_posix())
            except Exception as e:
                return f"Not okunurken hata oluştu: {e}"

            outbound = []
            outbound_raw = re.findall(r"\[\[(.*?)\]\]", content)
            for link in outbound_raw:
                clean_link = link.split("|")[0].split("#")[0].strip()
                if clean_link and clean_link not in outbound:
                    outbound.append(clean_link)

            # SQLite FTS5 tabanlı anında backlink sorgusu (sıfır disk taraması)
            raw_backlinks = self.search_engine.get_backlinks(rel_target.as_posix())
            raw_backlinks = list(dict.fromkeys([*raw_backlinks, *self.search_engine.get_backlinks(target_path.stem)]))
            if not raw_backlinks:
                self.search_engine.index_vault()
                raw_backlinks = self.search_engine.get_backlinks(rel_target.as_posix())
                raw_backlinks = list(dict.fromkeys([*raw_backlinks, *self.search_engine.get_backlinks(target_path.stem)]))
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
        """Handle one JSON-RPC request per line and survive malformed clients."""
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                req = json.loads(line)
            except (ValueError, UnicodeError):
                self._send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
                continue
            if (not isinstance(req, dict) or req.get('jsonrpc') != '2.0'
                    or not isinstance(req.get('method'), str)
                    or ('id' in req and req['id'] is not None and type(req['id']) not in (str, int))):
                self._send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}})
                continue
            if 'id' not in req:
                continue
            req_id, method, params = req['id'], req['method'], req.get('params', {})
            if not isinstance(params, dict):
                self._send({'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32602, 'message': 'Invalid params'}})
                continue
            try:
                if method == 'initialize':
                    result = {'protocolVersion': self.PROTOCOL_VERSION, 'capabilities': {'tools': {}},
                              'serverInfo': {'name': self.SERVER_NAME, 'version': self.SERVER_VERSION}}
                elif method == 'ping':
                    result = {}
                elif method == 'tools/list':
                    result = {'tools': self.get_tools_manifest()}
                elif method == 'tools/call':
                    name, arguments = params.get('name'), params.get('arguments', {})
                    if not isinstance(name, str):
                        raise ValueError('Invalid tool name')
                    self._validate_arguments(name, arguments)
                    text = self.call_tool(name, arguments)
                    result = {'content': [{'type': 'text', 'text': text}],
                              'isError': text.startswith(('Hata', 'Bilinmeyen', 'Not yazılırken', 'Ders kaydedilirken', 'Dosya okunurken', 'Not okunurken'))}
                else:
                    self._send({'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32601, 'message': 'Method not found'}})
                    continue
                self._send({'jsonrpc': '2.0', 'id': req_id, 'result': result})
            except ValueError:
                self._send({'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32602, 'message': 'Invalid params'}})
            except Exception:
                self._send({'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32603, 'message': 'Tool execution failed'}})

    def _send(self, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False)
        sys.stdout.write(body + "\n")
        sys.stdout.flush()


def serve(ctx):
    RespectedMcpServer(ctx).run_stdio()
    return 0
