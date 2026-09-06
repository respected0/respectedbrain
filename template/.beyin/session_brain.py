"""Session Brain: Vault Dışı Hafif Oturum Arama Motoru.

AI oturum loglarını (Claude Code, ChatGPT, Codex vb.) vault'u şişirmeden
bağımsız bir dizinde (`~/.respectedos/session-brain/`) saklar ve indeksler.

Zaman Çürümesi (Recency Decay) + Terim Ağırlıklandırma (TF-IDF benzeri) formülüyle
"Geçen ay çözdüğümüz auth bug'ı" gibi oturumları anında bulur.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_SIDECAR_DIR = Path.home() / ".respectedos" / "session-brain"

_WORD_RE = re.compile(r"\w+")
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "to", "in", "on", "for", "with",
    "and", "or", "of", "this", "that", "it", "bir", "ve", "ile", "için",
    "de", "da", "bu", "şu", "o", "ne", "nasıl", "ben", "sen", "biz"
}


def _tokenize(text: str) -> List[str]:
    words = _WORD_RE.findall(text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


def _term_freqs(tokens: List[str]) -> Dict[str, float]:
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = max(1, len(tokens))
    return {t: c / total for t, c in counts.items()}


def _parse_timestamp(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            # ISO format dene
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass
    return datetime.now(timezone.utc).timestamp()


def _recency_decay(ts: float, half_life_days: float = 30.0) -> float:
    """Zaman çürümesi: gün geçtikçe puan düşer ama asla sıfırlanmaz."""
    now = datetime.now(timezone.utc).timestamp()
    age_days = max(0.0, (now - ts) / 86400.0)
    decay = math.exp(-0.693 * (age_days / half_life_days))
    # Taban puan %25 + %75 zaman faktörü
    return 0.25 + 0.75 * decay


class SessionBrain:
    def __init__(self, sidecar_dir: Optional[Path] = None):
        self.sidecar_dir = (sidecar_dir or DEFAULT_SIDECAR_DIR).resolve()
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.sidecar_dir / "index.json"
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.load_index()

    def load_index(self) -> None:
        if self.index_file.exists():
            try:
                self.sessions = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                self.sessions = {}
        else:
            self.sessions = {}

    def save_index(self) -> None:
        self.index_file.write_text(
            json.dumps(self.sessions, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def ingest_session(self, session_id: str, title: str, content: str, timestamp: Optional[float] = None, source: str = "") -> None:
        """Tek bir oturumu analiz edip indekse ekler."""
        ts = timestamp or datetime.now(timezone.utc).timestamp()
        tokens = _tokenize(f"{title} {content}")
        tf = _term_freqs(tokens)
        
        # En karakteristik ilk 20 anahtar kelime
        top_terms = sorted(tf.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Kısa özet (ilk 300 karakter)
        snippet = content.strip().replace("\n", " ")[:250] + ("..." if len(content) > 250 else "")
        
        self.sessions[session_id] = {
            "id": session_id,
            "title": title or "İsimsiz Oturum",
            "timestamp": ts,
            "date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "source": source,
            "snippet": snippet,
            "terms": dict(top_terms),
            "token_count": len(tokens)
        }

    def ingest_file(self, file_path: Path) -> int:
        """JSONL, JSON veya TXT/MD dosyasını ayrıştırıp içeri aktarır."""
        p = Path(file_path)
        if not p.exists():
            return 0
            
        count = 0
        if p.suffix == ".jsonl":
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    s_id = data.get("sessionId") or data.get("id") or f"{p.stem}_{count}"
                    title = data.get("title") or data.get("summary") or p.stem
                    text = data.get("text") or data.get("content") or str(data)
                    ts = _parse_timestamp(data.get("timestamp") or data.get("createdAt"))
                    self.ingest_session(str(s_id), title, text, ts, source=str(p))
                    count += 1
                except Exception:
                    continue
        elif p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, list):
                    for item in data:
                        s_id = item.get("id") or f"{p.stem}_{count}"
                        title = item.get("title") or p.stem
                        text = item.get("content") or str(item)
                        ts = _parse_timestamp(item.get("timestamp"))
                        self.ingest_session(str(s_id), title, text, ts, source=str(p))
                        count += 1
                elif isinstance(data, dict):
                    s_id = data.get("id") or p.stem
                    title = data.get("title") or p.stem
                    text = data.get("content") or str(data)
                    ts = _parse_timestamp(data.get("timestamp"))
                    self.ingest_session(str(s_id), title, text, ts, source=str(p))
                    count += 1
            except Exception:
                pass
        else:
            # Düz metin / Markdown
            text = p.read_text(encoding="utf-8", errors="ignore")
            s_id = p.stem
            self.ingest_session(s_id, p.stem, text, p.stat().st_mtime, source=str(p))
            count += 1
            
        self.save_index()
        return count

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Soruya en uygun geçmiş oturumları recency decay ile sıralar."""
        q_tokens = _tokenize(query_text)
        if not q_tokens or not self.sessions:
            return []
            
        results = []
        for s_id, s_data in self.sessions.items():
            terms = s_data.get("terms", {})
            
            # Anlamsal benzerlik skoru
            overlap_score = 0.0
            for qt in q_tokens:
                if qt in terms:
                    overlap_score += terms[qt] * 10.0
                elif any(qt in term for term in terms):
                    overlap_score += 1.0
                    
            if overlap_score <= 0:
                continue
                
            # Recency Decay
            decay = _recency_decay(s_data["timestamp"])
            final_score = overlap_score * decay
            
            results.append({
                "id": s_id,
                "title": s_data["title"],
                "date": s_data["date"],
                "score": round(final_score, 3),
                "similarity": round(overlap_score, 3),
                "recency_multiplier": round(decay, 2),
                "snippet": s_data["snippet"],
                "source": s_data["source"]
            })
            
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


def main():
    parser = argparse.ArgumentParser(description="Session Brain oturum arama motoru.")
    subparsers = parser.add_subparsers(dest="subcommand")
    
    # Ingest
    ingest_p = subparsers.add_parser("ingest", help="Dosya veya oturum indeksle")
    ingest_p.add_argument("path", help="İndekslenecek dosya yolu (.jsonl, .json, .md)")
    ingest_p.add_argument("--sidecar", default=None, help="Sidecar dizini")
    
    # Query
    query_p = subparsers.add_parser("query", help="Geçmiş oturumlarda arama yap")
    query_p.add_argument("query", help="Aranacak konu")
    query_p.add_argument("--sidecar", default=None, help="Sidecar dizini")
    query_p.add_argument("--json", action="store_true", help="JSON formatında çıktı")
    query_p.add_argument("--top", type=int, default=5, help="Dönecek sonuç sayısı")
    
    # List
    list_p = subparsers.add_parser("list", help="İndekslenmiş oturumları listele")
    list_p.add_argument("--sidecar", default=None, help="Sidecar dizini")
    
    args = parser.parse_args()
    sidecar = Path(args.sidecar) if getattr(args, "sidecar", None) else DEFAULT_SIDECAR_DIR
    sb = SessionBrain(sidecar)
    
    if args.subcommand == "ingest":
        n = sb.ingest_file(Path(args.path))
        print(f"Başarılı: {n} oturum sidecar indeksine eklendi -> {sb.index_file}")
    elif args.subcommand == "query":
        res = sb.query(args.query, top_k=args.top)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"=== SESSION BRAIN ARAMA: '{args.query}' ===")
            if not res:
                print("Eşleşen oturum bulunamadı.")
            for r in res:
                print(f"\n[{r['date']}] {r['title']} (Skor: {r['score']} | Benzerlik: {r['similarity']} | Taze: {r['recency_multiplier']})")
                print(f"  ID: {r['id']}")
                print(f"  Özet: {r['snippet']}")
    elif args.subcommand == "list":
        print(f"Kayıtlı Oturum Sayısı: {len(sb.sessions)} (Konum: {sb.sidecar_dir})")
        for s in list(sb.sessions.values())[:15]:
            print(f"  • [{s['date']}] {s['title']} ({s['id']})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
