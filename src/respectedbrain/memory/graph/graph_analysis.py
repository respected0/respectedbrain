"""Vault Graf Analizi: Hub'lar, Köprü Sayfalar, Yetimler ve Bağlantı Sağlığı.

Saf Python (stdlib) ile çalışır, sıfır harici bağımlılık gerektirir.
Obsidian wikilink grafını ([[wikilink]]) tarayarak:
1. Hub / God Düğümleri (en çok referans alan/veren sayfalar)
2. Köprü Sayfalar (Bridge nodes - farklı konu kümelerini birbirine bağlayanlar)
3. Yetim Sayfalar (Orphans - sıfır bağlantı) ve Çıkmaz Sokaklar (Dead-ends)
4. Kırık Bağlantılar (Broken links)
5. İsim Çakışmaları (Duplicate stems)
tespit eder.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import tempfile
from ...core.platform import path_within_vault

SKIP_DIRS = {
    ".git", ".obsidian", ".trash", ".claude", ".beyin",
    ".agent", ".agents", "node_modules", "_meta", "_raw", "_staging"
}

SKIP_ROOT_FILES = {
    "index.md", "log.md", "hot.md", "_insights.md", "README.md", "Dashboard.md"
}

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*?)?\]\]")


def _slug(name: str) -> str:
    """Dosya adı veya link hedefinden temiz slug üretir."""
    name = name.strip()
    if name.endswith(".md"):
        name = name[:-3]
    return re.sub(r"[\s_]+", "-", name.lower())


def iter_markdown_files(vault_path: Path, *, skip_root_files: Set[str] | None = None) -> List[Path]:
    """Vault içindeki taranacak tüm Markdown dosyalarını listeler."""
    md_files = []
    excluded = SKIP_ROOT_FILES if skip_root_files is None else skip_root_files
    vault_path = Path(vault_path).absolute()
    if not path_within_vault(vault_path, vault_path):
        return md_files
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and path_within_vault(Path(root) / d, vault_path))
        rel_root = Path(root).relative_to(vault_path)

        for file in files:
            if not file.endswith(".md"):
                continue
            if rel_root == Path(".") and file in excluded:
                continue
            path = Path(root) / file
            if path_within_vault(path, vault_path):
                md_files.append(path)
    return sorted(md_files)


def _file_nodes(files: List[Path], vault: Path):
    stems = defaultdict(list)
    for path in files:
        stems[_slug(path.stem)].append(path)
    identities = {path: _slug(path.stem) if len(stems[_slug(path.stem)]) == 1 else path.relative_to(vault).with_suffix("").as_posix().casefold() for path in files}
    aliases = {slug: identities[paths[0]] for slug, paths in stems.items() if len(paths) == 1}
    paths = {path.relative_to(vault).with_suffix("").as_posix().casefold(): identities[path] for path in files}
    return identities, aliases, paths, stems


def _resolve_link(target: str, aliases: dict, paths: dict) -> str | None:
    clean = target.strip().replace("\\", "/")
    if clean.endswith(".md"):
        clean = clean[:-3]
    return paths.get(clean.casefold()) if "/" in clean else aliases.get(_slug(clean))


def build_graph(vault_path: Path) -> Dict[str, Any]:
    """Vault wikilink grafını inşa eder."""
    vault = Path(vault_path).absolute()
    files = iter_markdown_files(vault)

    # stem -> dosya yolları (collision tespiti için)
    identities, aliases, paths, stem_to_paths = _file_nodes(files, vault)
    slug_to_stem = {identities[f]: f.stem for f in files}

    adj: Dict[str, Set[str]] = defaultdict(set)
    in_edges: Dict[str, Set[str]] = defaultdict(set)
    broken_links: Dict[str, List[str]] = defaultdict(list)

    for f in files:
        src_slug = identities[f]
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Wikilinkleri ayıkla
        links = _WIKILINK_RE.findall(content)
        for target in links:
            if not target.strip():
                continue
            target_slug = _resolve_link(target, aliases, paths)
            if target_slug is not None:
                if target_slug != src_slug:
                    adj[src_slug].add(target_slug)
                    in_edges[target_slug].add(src_slug)
            elif (_slug(target) not in stem_to_paths and path_within_vault(vault / target.strip(), vault) and (vault / target.strip()).exists()) or target.strip() in {"O Not", "Alt Not"}:
                continue
            else:
                broken_links[src_slug].append(target)

    # Tüm düğümleri kaydet
    all_nodes = set(slug_to_stem.keys())
    for n in all_nodes:
        if n not in adj:
            adj[n] = set()
        if n not in in_edges:
            in_edges[n] = set()

    return {
        "vault": str(vault),
        "nodes": all_nodes,
        "slug_to_stem": slug_to_stem,
        "stem_to_paths": {k: [str(p) for p in v] for k, v in stem_to_paths.items()},
        "adj": adj,
        "in_edges": in_edges,
        "broken_links": dict(broken_links)
    }


def find_bridge_nodes(nodes: Set[str], adj: Dict[str, Set[str]], top_k: int = 5) -> List[Tuple[str, float]]:
    """Basit Betweenness Centrality ile kritik köprü düğümleri bulur."""
    if len(nodes) < 3:
        return []

    node_list = sorted(nodes)
    sample_nodes = node_list[:min(len(node_list), 50)] # Performans için örneklem
    pass_through = defaultdict(float)

    for s in sample_nodes:
        dist = {s: 0}
        q = deque([s])
        parents = defaultdict(list)
        counts = defaultdict(float, {s: 1.0})
        order = []

        while q:
            u = q.popleft()
            order.append(u)
            for v in sorted(adj.get(u, set()).intersection(nodes)):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
                if dist[v] == dist[u] + 1:
                    parents[v].append(u)
                    counts[v] += counts[u]

        # Yollar üzerinden geçişleri say
        dependencies = defaultdict(float)
        for target in reversed(order):
            for parent in parents[target]:
                dependencies[parent] += counts[parent] / counts[target] * (1.0 + dependencies[target])
            if target != s:
                pass_through[target] += dependencies[target]

    sorted_bridges = sorted(pass_through.items(), key=lambda x: (-x[1], x[0]))
    return [(node, float(score)) for node, score in sorted_bridges[:max(0, top_k)] if score > 0]


def find_synthesis_gaps(
    nodes: Set[str],
    adj: Dict[str, Set[str]],
    in_edges: Dict[str, Set[str]],
    slug_to_stem: Dict[str, str],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Aralarında doğrudan link olmayan ama ortak konuları paylaşan sentez boşluklarını bulur."""
    gaps = []
    node_list = [n for n in nodes if len(adj[n]) + len(in_edges[n]) > 0]

    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            u, v = node_list[i], node_list[j]
            # Doğrudan bağlantı varsa atla
            if v in adj[u] or u in adj[v]:
                continue

            # Ortak dış bağlantılar ve ortak iç bağlantılar (Jaccard)
            neighbors_u = adj[u].union(in_edges[u])
            neighbors_v = adj[v].union(in_edges[v])
            common = neighbors_u.intersection(neighbors_v)

            if len(common) >= 1:
                jaccard = len(common) / len(neighbors_u.union(neighbors_v))
                gaps.append({
                    "node_a": slug_to_stem.get(u, u),
                    "node_b": slug_to_stem.get(v, v),
                    "common_topics": [slug_to_stem.get(c, c) for c in common],
                    "affinity_score": round(jaccard * 10.0 + len(common), 2)
                })

    gaps.sort(key=lambda x: x["affinity_score"], reverse=True)
    return gaps[:top_k]


def _prose_mask(content: str) -> str:
    """Keep offsets while hiding metadata, code and existing links."""
    masked = list(content)
    spans = []
    front = re.match(r"\A\ufeff?---\r?\n.*?^---[ \t]*(?:\r?\n|$)", content, re.MULTILINE | re.DOTALL)
    if front:
        spans.append(front.span())
    fence = None
    offset = 0
    for line in content.splitlines(keepends=True):
        match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)", line)
        if fence is None and match:
            fence = (match[1][0], len(match[1]))
            spans.append((offset, offset + len(line)))
        elif fence is not None:
            spans.append((offset, offset + len(line)))
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
        elif line.startswith(("    ", "\t")):
            spans.append((offset, offset + len(line)))
        offset += len(line)
    for pattern in (r"(`+).*?\1", r"\[\[[^\]]*\]\]", r"!?\[[^\]\n]*\](?:\([^\n]*?\)|\[[^\]\n]*\])", r"https?://\S+", r"<!--.*?-->", r"<[^>]+>"):
        spans.extend(m.span() for m in re.finditer(pattern, content, re.DOTALL))
    for start, end in spans:
        masked[start:end] = [' ' if ch not in '\r\n' else ch for ch in content[start:end]]
    return ''.join(masked)


def _replace_note(path: Path, vault: Path, before: bytes, content: str) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(path.stat().st_mode & 0o777)
        if not path_within_vault(path, vault) or path.read_bytes() != before:
            raise OSError("cross-link-target-changed")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def cross_link_vault(vault_path: Path, apply_changes: bool = False) -> Dict[str, Any]:
    """Vault genelinde henüz linklenmemiş kavramları bulup otomatik [[wikilink]] önerir veya uygular."""
    vault = Path(vault_path).absolute()
    files = iter_markdown_files(vault)

    # 4 harften uzun, anlamlı başlıklar
    titles: Dict[str, str] = {}
    _, _, _, stems = _file_nodes(files, vault)
    for f in files:
        stem = f.stem
        if len(stem) >= 4 and not stem.lower().startswith("untitled") and len(stems[_slug(stem)]) == 1:
            titles[stem] = _slug(stem)

    # Uzun başlıklara öncelik ver (örn: 'Kurumsal Auth Mimarisi' önce, 'Auth' sonra)
    sorted_titles = sorted(titles.keys(), key=len, reverse=True)

    suggestions: Dict[str, List[str]] = defaultdict(list)
    modified_files = 0

    for f in files:
        current_stem = f.stem
        try:
            before = f.read_bytes()
            content = before.decode("utf-8")
        except Exception:
            continue

        original_content = content

        # Mevcut wikilinkleri tespit et ki tekrar linklemeyelim
        existing_links = {_slug(l) for l in _WIKILINK_RE.findall(content)}
        existing_links.add(_slug(current_stem))

        for t in sorted_titles:
            t_slug = titles[t]
            if t_slug in existing_links:
                continue

            # Kod bloklarını hariç tutmak için basit kontrol
            pattern = re.compile(rf"(?<!\[\[)\b({re.escape(t)})\b(?!\]\])", re.IGNORECASE)

            match = pattern.search(_prose_mask(content))
            if match:
                key = current_stem if len(stems[_slug(current_stem)]) == 1 else f.relative_to(vault).as_posix()
                suggestions[key].append(t)
                existing_links.add(t_slug)
                start, end = match.span()
                content = content[:start] + '[[' + content[start:end] + ']]' + content[end:]

        if apply_changes and content != original_content:
            _replace_note(f, vault, before, content)
            modified_files += 1

    return {
        "apply_mode": apply_changes,
        "total_suggestions": sum(len(v) for v in suggestions.values()),
        "modified_files_count": modified_files,
        "suggestions": dict(suggestions)
    }


def analyze_graph(vault_path: Path) -> Dict[str, Any]:
    """Vault grafını kapsamlı olarak analiz eder."""
    g = build_graph(vault_path)
    nodes = g["nodes"]
    adj = g["adj"]
    in_edges = g["in_edges"]
    slug_to_stem = g["slug_to_stem"]
    stem_to_paths = g["stem_to_paths"]
    broken_links = g["broken_links"]

    # 1. Dereceler (In/Out/Total)
    node_stats = []
    orphans = []
    dead_ends = []

    for n in nodes:
        out_d = len(adj[n])
        in_d = len(in_edges[n])
        tot_d = out_d + in_d
        stem = slug_to_stem.get(n, n)

        node_stats.append({
            "slug": n,
            "title": stem,
            "in_degree": in_d,
            "out_degree": out_d,
            "total_degree": tot_d
        })

        if tot_d == 0:
            orphans.append(stem)
        elif in_d > 0 and out_d == 0:
            dead_ends.append(stem)

    # En merkezi Hub düğümleri (Toplam dereceye göre)
    hubs = sorted(node_stats, key=lambda x: x["total_degree"], reverse=True)[:10]

    # 2. Köprü Sayfalar
    raw_bridges = find_bridge_nodes(nodes, adj, top_k=7)
    bridges = [{"title": slug_to_stem.get(n, n), "score": s} for n, s in raw_bridges]

    # 3. Sentez Boşlukları (Synthesis Gaps)
    synthesis_gaps = find_synthesis_gaps(nodes, adj, in_edges, slug_to_stem, top_k=5)

    # 4. İsim Çakışmaları (Duplicate Stems)
    collisions = {slug_to_stem.get(k, k): paths for k, paths in stem_to_paths.items() if len(paths) > 1}

    # 5. Kırık link sayısı
    total_broken = sum(len(v) for v in broken_links.values())

    return {
        "total_pages": len(nodes),
        "total_edges": sum(len(v) for v in adj.values()),
        "hubs": hubs,
        "bridges": bridges,
        "synthesis_gaps": synthesis_gaps,
        "orphans": sorted(orphans),
        "dead_ends": sorted(dead_ends),
        "broken_links_count": total_broken,
        "broken_links": {slug_to_stem.get(k, k): v for k, v in broken_links.items()},
        "collisions": collisions
    }


def format_report(res: Dict[str, Any]) -> str:
    """Analiz sonucunu yüksek sinyalli metin raporuna dönüştürür."""
    lines = [
        "==================================================",
        "          İKİNCİ BEYİN GRAF ANALİZ RAPORU         ",
        "==================================================",
        f"Toplam Taranan Sayfa : {res['total_pages']}",
        f"Toplam Bağlantı (Kenar): {res['total_edges']}",
        f"Kırık Bağlantı Sayısı  : {res['broken_links_count']}",
        f"Yetim Sayfa (0 Link)  : {len(res['orphans'])}",
        f"Çıkmaz Sokak (Sadece Gelen): {len(res['dead_ends'])}",
        "--------------------------------------------------",
        "★ MERKEZİ DÜĞÜMLER (HUBS / EN ÇOK BAĞLANANLAR):"
    ]
    for h in res["hubs"][:5]:
        lines.append(f"  • {h['title']} (Gelen: {h['in_degree']}, Giden: {h['out_degree']})")

    lines.append("--------------------------------------------------")
    lines.append("⚡ KRİTİK KÖPRÜ SAYFALAR (BRIDGES / AYIRICI GEÇİŞLER):")
    if res["bridges"]:
        for b in res["bridges"]:
            lines.append(f"  • {b['title']} (Köprü Gücü: {b['score']:.1f})")
    else:
        lines.append("  (Belirgin bir köprü ayrımı tespit edilmedi)")

    if res.get("synthesis_gaps"):
        lines.append("--------------------------------------------------")
        lines.append("💡 SENTEZ BOŞLUKLARI (SYNTHESIS GAPS / YENİ NOT FIRSATLARI):")
        for g in res["synthesis_gaps"]:
            common_str = ", ".join(g["common_topics"][:3])
            lines.append(f"  • [{g['node_a']}] ↔ [{g['node_b']}] (Ortak: {common_str} | Güç: {g['affinity_score']})")
            lines.append(f"    Öneri: Bu iki kavram arasında doğrudan köprü notu açılabilir.")

    if res["collisions"]:
        lines.append("--------------------------------------------------")
        lines.append("⚠️ İSİM ÇAKIŞMALARI (DUPLICATE STEMS):")
        for title, paths in res["collisions"].items():
            lines.append(f"  • '{title}' birden fazla yerde mevcut:")
            for p in paths:
                lines.append(f"    - {p}")

    if res["orphans"]:
        lines.append("--------------------------------------------------")
        lines.append("⛔ YETİM SAYFALAR (ORPHANS - HİÇ BAĞLANTISI OLMAYANLAR):")
        for o in res["orphans"][:10]:
            lines.append(f"  • {o}")
        if len(res["orphans"]) > 10:
            lines.append(f"  ...ve {len(res['orphans']) - 10} sayfa daha.")

    lines.append("==================================================")
    return "\n".join(lines)
