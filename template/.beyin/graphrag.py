"""GraphRAG: Bellek İçi Ön-Eleme ve Akıllı Sayfa Seçim Motoru.

Gereksiz dosya okumasını ve LLM context şişmesini önler.
Frontmatter (başlık, etiketler, özet) ve wikilink bağlantılarından
hızlı bir bellek içi indeks oluşturur.

Soru sorulduğunda:
1. Soru terimlerini analiz eder.
2. Sadece okunması gereken 2-3 sayfayı (`should_read`) belirler.
3. Özetler yeterliyse `index_only: true` döner, gövde okumayı tamamen atlar.
4. İki kavram arasındaki anlamsal yolu (`find_path`) çıkarabilir.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKIP_DIRS = {
    ".git", ".obsidian", ".trash", ".claude", ".beyin",
    ".agent", ".agents", "node_modules", "_meta", "_raw", "_staging"
}

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*?)?\]\]")
_FRONT_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_TAGS_RE = re.compile(r"^tags:\s*\[([^\]]+)\]", re.MULTILINE)
_TAGS_LIST_RE = re.compile(r"^tags:\s*\n((?:\s+-\s+\S+\n)+)", re.MULTILINE)
_CATEGORY_RE = re.compile(r"^category:\s*(\w+)", re.MULTILINE)
_SUMMARY_RE = re.compile(r"^summary:\s*[\"']?(.*?)[\"']?$", re.MULTILINE)
_TITLE_RE = re.compile(r"^title:\s*[\"']?(.*?)[\"']?$", re.MULTILINE)

_STOP_WORDS = {
    "bu", "şu", "o", "ve", "ile", "için", "bir", "de", "da", "mi", "mı",
    "ne", "nasıl", "neden", "kim", "hangi", "var", "yok", "the", "a", "an",
    "and", "or", "in", "on", "at", "to", "for", "with", "about", "what", "how",
    "why", "is", "are", "hakkında", "neler", "biliyorum", "biliyoruz"
}


def _slug(name: str) -> str:
    name = name.strip()
    if name.endswith(".md"):
        name = name[:-3]
    return re.sub(r"[\s_]+", "-", name.lower())


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"\w+", text.lower())
    return {w for w in words if len(w) > 1 and w not in _STOP_WORDS}


def build_index(vault_path: Path) -> Dict[str, Any]:
    """Vault sayfalarının özetlerini ve linklerini bellek içi indekse toplar."""
    vault = Path(vault_path).resolve()
    pages: Dict[str, Dict[str, Any]] = {}
    adj: Dict[str, Set[str]] = defaultdict(set)
    
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for file in files:
            if not file.endswith(".md") or file in {"index.md", "log.md", "hot.md"}:
                continue
                
            full_path = Path(root) / file
            slug = _slug(full_path.stem)
            
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
                
            title = full_path.stem
            tags: List[str] = []
            category = ""
            summary = ""
            
            # Frontmatter ayrıştırma
            front_match = _FRONT_RE.match(content)
            if front_match:
                front_text = front_match.group(1)
                
                t_m = _TITLE_RE.search(front_text)
                if t_m:
                    title = t_m.group(1).strip()
                    
                c_m = _CATEGORY_RE.search(front_text)
                if c_m:
                    category = c_m.group(1).strip()
                    
                s_m = _SUMMARY_RE.search(front_text)
                if s_m:
                    summary = s_m.group(1).strip()
                    
                # Tags listesi
                t_arr = _TAGS_RE.search(front_text)
                if t_arr:
                    tags = [t.strip().strip("'\"") for t in t_arr.group(1).split(",") if t.strip()]
                else:
                    t_list = _TAGS_LIST_RE.search(front_text)
                    if t_list:
                        tags = [line.strip().lstrip("- ").strip("'\"") for line in t_list.group(1).splitlines() if line.strip()]
                        
            # Wikilinkleri al
            links = set()
            for l in _WIKILINK_RE.findall(content):
                target_slug = _slug(l)
                if target_slug and target_slug != slug:
                    links.add(target_slug)
                    adj[slug].add(target_slug)
                    
            pages[slug] = {
                "slug": slug,
                "title": title,
                "path": str(full_path),
                "rel_path": str(full_path.relative_to(vault)),
                "category": category,
                "tags": tags,
                "summary": summary,
                "links": list(links),
                "tokens": _tokenize(f"{title} {' '.join(tags)} {summary}")
            }
            
    return {"pages": pages, "adj": dict(adj)}


def find_path(index: Dict[str, Any], source: str, target: str) -> Optional[List[str]]:
    """İki sayfa arasındaki en kısa bağlantı yolunu (BFS) döner."""
    s_slug = _slug(source)
    t_slug = _slug(target)
    adj = index.get("adj", {})
    
    if s_slug not in index["pages"] or t_slug not in index["pages"]:
        return None
        
    queue = deque([[s_slug]])
    visited = {s_slug}
    
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == t_slug:
            pages = index["pages"]
            return [pages[slug]["title"] for slug in path]
            
        for neighbor in adj.get(node, []):
            if neighbor not in visited and neighbor in index["pages"]:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return None


def query_vault(vault_path: Path, question: str, max_read: int = 3) -> Dict[str, Any]:
    """Soruya en uygun sayfaları ve should_read önerilerini döner."""
    index = build_index(vault_path)
    q_tokens = _tokenize(question)
    
    if not q_tokens:
        return {
            "answer_type": "none",
            "candidates": [],
            "should_read": [],
            "index_only": False,
            "message": "Soru terimleri çok kısa veya ayırt edici değil."
        }
        
    candidates = []
    
    for slug, meta in index["pages"].items():
        score = 0.0
        
        # 1. Başlık eşleşmesi
        title_tokens = _tokenize(meta["title"])
        common_title = q_tokens.intersection(title_tokens)
        if common_title:
            score += len(common_title) * 4.0
            
        # 2. Tag eşleşmesi
        tag_tokens = _tokenize(" ".join(meta["tags"]))
        common_tags = q_tokens.intersection(tag_tokens)
        if common_tags:
            score += len(common_tags) * 3.0
            
        # 3. Özet eşleşmesi
        summary_tokens = _tokenize(meta["summary"])
        common_summary = q_tokens.intersection(summary_tokens)
        if common_summary:
            score += len(common_summary) * 2.0
            
        # 4. Hub bonusu (Daha çok bağlantı = daha merkezi bilgi)
        score += min(len(meta["links"]) * 0.1, 1.0)
        
        if score > 0:
            candidates.append({
                "title": meta["title"],
                "path": meta["path"],
                "rel_path": meta["rel_path"],
                "summary": meta["summary"],
                "score": round(score, 2),
                "tags": meta["tags"]
            })
            
    # Skora göre sırala
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidates[:max_read]
    
    # index_only kararı: En iyi adayın özeti varsa ve soru terimlerinin çoğunu kapsıyorsa
    index_only = False
    if top_candidates and top_candidates[0]["summary"]:
        best_summary_tokens = _tokenize(top_candidates[0]["summary"])
        if len(q_tokens.intersection(best_summary_tokens)) >= max(1, len(q_tokens) // 2):
            index_only = True
            
    should_read = [c["rel_path"] for c in top_candidates if not index_only]
    
    return {
        "question": question,
        "total_matches": len(candidates),
        "candidates": top_candidates,
        "should_read": should_read,
        "index_only": index_only
    }


def main():
    parser = argparse.ArgumentParser(description="GraphRAG hafif bellek sorgu motoru.")
    parser.add_argument("vault", help="Vault dizini")
    parser.add_argument("question", nargs="?", help="Sorgu sorusu")
    parser.add_argument("--path", nargs=2, metavar=("KAYNAK", "HEDEF"), help="İki kavram arasındaki yolu bulur")
    parser.add_argument("--json", action="store_true", help="JSON çıktısı verir")
    parser.add_argument("--max-read", type=int, default=3, help="Maksimum okunacak sayfa sayısı")
    args = parser.parse_args()
    
    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"Hata: Vault dizini bulunamadı: {vault_path}", file=sys.stderr)
        sys.exit(1)
        
    if args.path:
        idx = build_index(vault_path)
        p = find_path(idx, args.path[0], args.path[1])
        if args.json:
            print(json.dumps({"from": args.path[0], "to": args.path[1], "path": p}, indent=2, ensure_ascii=False))
        else:
            if p:
                print(" -> ".join(p))
            else:
                print(f"'{args.path[0]}' ile '{args.path[1]}' arasında bağlantı yolu bulunamadı.")
        return
        
    if not args.question:
        parser.print_help()
        sys.exit(1)
        
    res = query_vault(vault_path, args.question, max_read=args.max_read)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("=== GRAPHRAG SORGULAMA SONUCU ===")
        print(f"Soru: {res['question']}")
        print(f"İndeks-Yalnızca Yanıtlanabilir mi?: {'EVET (Gövde okumaya gerek yok)' if res['index_only'] else 'HAYIR'}")
        print("\nÖnerilen Sayfalar (Should Read):")
        if res["should_read"]:
            for p in res["should_read"]:
                print(f"  📖 {p}")
        else:
            print("  (Açılması gereken dosya yok, özetler yeterli)")
            
        print("\nEn İyi Adaylar:")
        for c in res["candidates"]:
            print(f"  • {c['title']} [Skor: {c['score']}] -> {c['rel_path']}")
            if c["summary"]:
                print(f"    Özet: {c['summary']}")


if __name__ == "__main__":
    main()
