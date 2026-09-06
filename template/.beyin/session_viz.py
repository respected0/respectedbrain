"""Session Viz: Oturum Grafiğini İnteraktif HTML Olarak Görselleştirici.

`session_brain.py` tarafından üretilen sidecar indeksini okur,
kullanıcının tarayıcısında açabileceği tek dosyalık interaktif bir
vis.js ağı (zaman kaydırıcılı, canlı aramalı, koyu temalı) üretir.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_SIDECAR_DIR = Path.home() / ".respectedos" / "session-brain"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RespectedOS Session Graph</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f1117;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      height: 100vh;
      overflow: hidden;
    }
    #sidebar {
      width: 340px;
      background: #161b22;
      border-right: 1px solid #30363d;
      display: flex;
      flex-direction: column;
      padding: 16px;
      gap: 14px;
      z-index: 10;
    }
    h2 { font-size: 1.1rem; color: #58a6ff; }
    input[type="text"] {
      width: 100%;
      padding: 8px 12px;
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 6px;
      color: #fff;
      font-size: 0.9rem;
    }
    .slider-box {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.8rem;
      color: #8b949e;
    }
    input[type="range"] { width: 100%; accent-color: #58a6ff; }
    #details {
      flex: 1;
      overflow-y: auto;
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 12px;
      font-size: 0.85rem;
      line-height: 1.5;
    }
    #network { flex: 1; height: 100%; position: relative; }
    .badge {
      display: inline-block;
      background: #238636;
      color: #fff;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.75rem;
    }
  </style>
</head>
<body>
  <div id="sidebar">
    <h2>🧠 RespectedOS Oturum Grafı</h2>
    <input type="text" id="search" placeholder="Oturum veya konu ara...">
    <div class="slider-box">
      <span>Zaman Filtresi (Son N Gün): <b id="daysVal">Tümü</b></span>
      <input type="range" id="timeSlider" min="1" max="180" value="180">
    </div>
    <div id="details">
      <p style="color:#8b949e;">Detaylarını görmek için grafikteki bir oturum düğümüne tıklayın.</p>
    </div>
  </div>
  <div id="network"></div>

  <script>
    const rawSessions = __SESSIONS_JSON__;
    const sessionList = Object.values(rawSessions);

    // Düğümleri oluştur
    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();

    const now = Date.now() / 1000;

    sessionList.forEach(s => {
      const ageDays = Math.max(0, (now - s.timestamp) / 86400);
      nodes.add({
        id: s.id,
        label: s.title.length > 25 ? s.title.substring(0, 22) + '...' : s.title,
        title: s.title,
        timestamp: s.timestamp,
        ageDays: ageDays,
        shape: 'dot',
        size: 14,
        color: {
          background: '#58a6ff',
          border: '#1f6feb',
          highlight: { background: '#2ea043', border: '#3fb950' }
        },
        font: { color: '#c9d1d9', size: 12 }
      });
    });

    // Ortak terimleri olan oturumları birbirine bağla
    for (let i = 0; i < sessionList.length; i++) {
      for (let j = i + 1; j < sessionList.length; j++) {
        const s1 = sessionList[i];
        const s2 = sessionList[j];
        const t1 = Object.keys(s1.terms || {});
        const t2 = new Set(Object.keys(s2.terms || {}));
        const common = t1.filter(x => t2.has(x));

        if (common.length >= 2) {
          edges.add({
            from: s1.id,
            to: s2.id,
            value: common.length,
            color: { color: 'rgba(110, 118, 129, 0.4)', highlight: '#58a6ff' },
            title: 'Ortak Konular: ' + common.join(', ')
          });
        }
      }
    }

    const container = document.getElementById('network');
    const data = { nodes, edges };
    const options = {
      nodes: { borderWidth: 2 },
      edges: { smooth: { type: 'continuous' } },
      physics: {
        stabilization: { iterations: 100 },
        barnesHut: { gravitationalConstant: -3000, springLength: 120 }
      },
      interaction: { hover: true, tooltipDelay: 200 }
    };

    const network = new vis.Network(container, data, options);

    // Tıklama olayı
    network.on('click', function(params) {
      if (params.nodes.length > 0) {
        const sId = params.nodes[0];
        const s = rawSessions[sId];
        if (s) {
          const terms = Object.keys(s.terms || {}).slice(0, 8).map(t => `<span class="badge">${t}</span>`).join(' ');
          document.getElementById('details').innerHTML = `
            <h3 style="color:#58a6ff; margin-bottom:8px;">${s.title}</h3>
            <p><b>Tarih:</b> ${s.date || 'Bilinmiyor'}</p>
            <p><b>ID:</b> <code>${s.id}</code></p>
            <hr style="border:0; border-top:1px solid #30363d; margin:8px 0;">
            <p><b>Özet:</b></p>
            <p style="margin-top:4px; color:#c9d1d9;">${s.snippet || 'Özet bulunmuyor.'}</p>
            <hr style="border:0; border-top:1px solid #30363d; margin:8px 0;">
            <p><b>Anahtar Konular:</b></p>
            <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:6px;">${terms}</div>
          `;
        }
      }
    });

    // Arama filtreleme
    document.getElementById('search').addEventListener('input', function(e) {
      const q = e.target.value.toLowerCase().trim();
      nodes.forEach(node => {
        const full = rawSessions[node.id];
        const match = !q || full.title.toLowerCase().includes(q) || full.snippet.toLowerCase().includes(q);
        nodes.update({ id: node.id, hidden: !match });
      });
    });

    // Zaman filtresi
    document.getElementById('timeSlider').addEventListener('input', function(e) {
      const maxDays = parseInt(e.target.value);
      document.getElementById('daysVal').innerText = maxDays >= 180 ? 'Tümü' : maxDays + ' gün';
      nodes.forEach(node => {
        const hidden = maxDays < 180 && node.ageDays > maxDays;
        nodes.update({ id: node.id, hidden: hidden });
      });
    });
  </script>
</body>
</html>
"""


def render_html(index_path: Path, output_html: Path) -> Path:
    """Sidecar index.json dosyasından interaktif HTML görselleştirmesi üretir."""
    if not index_path.exists():
        raise FileNotFoundError(f"Session Brain indeksi bulunamadı: {index_path}")
        
    sessions = json.loads(index_path.read_text(encoding="utf-8"))
    json_payload = json.dumps(sessions, ensure_ascii=False)
    
    html_content = HTML_TEMPLATE.replace("__SESSIONS_JSON__", json_payload)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html_content, encoding="utf-8")
    return output_html


def main():
    parser = argparse.ArgumentParser(description="Session Brain HTML Görselleştirici.")
    parser.add_argument("--sidecar", default=None, help="Sidecar dizini")
    parser.add_argument("--output", "-o", default="session-graph.html", help="Çıktı HTML dosya yolu")
    args = parser.parse_args()
    
    sidecar_dir = Path(args.sidecar) if args.sidecar else DEFAULT_SIDECAR_DIR
    index_file = sidecar_dir / "index.json"
    output_path = Path(args.output).resolve()
    
    if not index_file.exists():
        print(f"Uyarı: Henüz indekslenmiş oturum yok ({index_file}). Önce 'session_brain.py ingest' çalıştırın.", file=sys.stderr)
        # Örnek boş şablon oluştur
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text("{}", encoding="utf-8")
        
    out = render_html(index_file, output_path)
    print(f"Başarılı: İnteraktif oturum grafiği oluşturuldu -> {out}")


if __name__ == "__main__":
    main()
