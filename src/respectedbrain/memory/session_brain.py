"""Session Brain: Vault Dışı Hafif Oturum Arama Motoru.

AI oturum loglarını (Claude Code, ChatGPT, Codex vb.) vault'u şişirmeden
AppContext'in UUID cache kökündeki `session-brain/` dizininde veya açıkça
verilen bağımsız bir dizinde saklar ve indeksler.

Zaman Çürümesi (Recency Decay) + Terim Ağırlıklandırma (TF-IDF benzeri) formülüyle
"Geçen ay çözdüğümüz auth bug'ı" gibi oturumları anında bulur.
"""

from __future__ import annotations

from contextlib import nullcontext
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..core.context import AppContext
from ..core.config import atomic_write_json
from ..core.coordination import writer_lease
from ..core.locking import exclusive_lock
from ..core.platform import path_within_vault

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
        if math.isfinite(val):
            return float(val)
    if isinstance(val, str):
        try:
            # ISO format dene
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass
    return datetime.now(timezone.utc).timestamp()


def load_session_index(path: Path) -> Dict[str, Dict[str, Any]]:
    """Reject corrupt history instead of treating it as an empty index."""
    sessions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(sessions, dict):
        raise ValueError("session-index-not-object")
    for identity, item in sessions.items():
        if not isinstance(item, dict) or item.get("id") != identity:
            raise ValueError("invalid-session-identity")
        if any(not isinstance(item.get(field), str) for field in ("title", "date", "source", "snippet")):
            raise ValueError("invalid-session-text")
        timestamp = item.get("timestamp")
        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ValueError("invalid-session-timestamp")
        terms = item.get("terms")
        if not isinstance(terms, dict) or any(not isinstance(term, str) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0 for term, weight in terms.items()):
            raise ValueError("invalid-session-terms")
    return sessions


def _recency_decay(ts: float, half_life_days: float = 30.0) -> float:
    """Zaman çürümesi: gün geçtikçe puan düşer ama asla sıfırlanmaz."""
    now = datetime.now(timezone.utc).timestamp()
    age_days = max(0.0, (now - ts) / 86400.0)
    decay = math.exp(-0.693 * (age_days / half_life_days))
    # Taban puan %25 + %75 zaman faktörü
    return 0.25 + 0.75 * decay


class SessionBrain:
    def __init__(self, sidecar_dir: Path | AppContext):
        self.ctx = sidecar_dir if isinstance(sidecar_dir, AppContext) else None
        directory = self.ctx.paths.cache_dir / "session-brain" if self.ctx else Path(sidecar_dir).absolute()
        self.boundary = self.ctx.paths.data_root if self.ctx else directory.parent
        if not path_within_vault(directory, self.boundary):
            raise ValueError("unsafe-session-sidecar")
        self.sidecar_dir = directory
        self.index_file = self.sidecar_dir / "index.json"
        self.lock_file = self.sidecar_dir / ".index.lock"
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
        with writer_lease(self.ctx) if self.ctx else nullcontext():
            self._validate_paths()
            self.sidecar_dir.mkdir(parents=True, exist_ok=True)
            self.load_index()

    def _validate_paths(self) -> None:
        for path in (self.index_file, self.lock_file):
            if not path_within_vault(path, self.boundary):
                raise ValueError("unsafe-session-index")

    def load_index(self) -> None:
        self._validate_paths()
        with exclusive_lock(self.lock_file):
            self.sessions = load_session_index(self.index_file)
        self.sessions.update(self._pending)

    def save_index(self) -> None:
        with writer_lease(self.ctx) if self.ctx else nullcontext():
            self._validate_paths()
            with exclusive_lock(self.lock_file):
                self._validate_paths()
                current = load_session_index(self.index_file)
                current.update(self._pending)
                atomic_write_json(self.index_file, current)
                self.sessions = current
                self._pending.clear()

    def ingest_session(self, session_id: str, title: str, content: str, timestamp: Optional[float] = None, source: str = "") -> None:
        """Tek bir oturumu analiz edip indekse ekler."""
        ts = datetime.now(timezone.utc).timestamp() if timestamp is None else timestamp
        if not isinstance(ts, (int, float)) or not math.isfinite(ts):
            raise ValueError("invalid-session-timestamp")
        if not isinstance(session_id, str) or not session_id or any(not isinstance(value, str) for value in (title, content, source)):
            raise ValueError("invalid-session-input")
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
        self._pending[session_id] = self.sessions[session_id]

    def ingest_file(self, file_path: Path) -> int:
        """JSONL, JSON veya TXT/MD dosyasını ayrıştırıp içeri aktarır."""
        p = Path(file_path)
        if not p.exists():
            return 0

        count = 0
        def ingest_record(data) -> int:
            if not isinstance(data, dict):
                return 0
            try:
                identity = data.get("sessionId") or data.get("id") or f"{p.stem}_{count}"
                title = data.get("title") or data.get("summary") or p.stem
                text = data.get("text") or data.get("content") or str(data)
                timestamp = data.get("timestamp")
                if timestamp is None:
                    timestamp = data.get("createdAt")
                self.ingest_session(str(identity), title, text, _parse_timestamp(timestamp), source=str(p))
                return 1
            except (ValueError, TypeError, OverflowError, OSError):
                return 0
        if p.suffix == ".jsonl":
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    count += ingest_record(json.loads(line))
                except Exception:
                    continue
        elif p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, list):
                    for item in data:
                        count += ingest_record(item)
                elif isinstance(data, dict):
                    data.setdefault("id", p.stem)
                    count += ingest_record(data)
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
        if not q_tokens or not self.sessions or top_k <= 0:
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
