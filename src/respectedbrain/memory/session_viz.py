"""Session Viz: Oturum Grafiğini İnteraktif HTML Olarak Görselleştirici.

`session_brain.py` tarafından üretilen sidecar indeksini okur,
kullanıcının tarayıcısında açabileceği tek dosyalık interaktif bir
vis.js ağı (zaman kaydırıcılı, canlı aramalı, koyu temalı) üretir.
"""

from __future__ import annotations

import json
from pathlib import Path
from ..core.config import atomic_write_bytes
from ..core.platform import path_within_vault
from .session_brain import load_session_index

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>İkinci Beyin Oturum Grafı</title>
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
    <h2>🧠 İkinci Beyin Oturum Grafı</h2>
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
    function textElement(tag, text) {
      const element = document.createElement(tag);
      element.textContent = text;
      return element;
    }

    // Düğümleri oluştur
    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();

    const now = Date.now() / 1000;

    sessionList.forEach(s => {
      const ageDays = Math.max(0, (now - s.timestamp) / 86400);
      nodes.add({
        id: s.id,
        label: s.title.length > 25 ? s.title.substring(0, 22) + '...' : s.title,
        title: textElement('span', s.title),
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
            title: textElement('span', 'Ortak Konular: ' + common.join(', '))
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
          const details = document.getElementById('details');
          details.replaceChildren();
          const heading = textElement('h3', s.title);
          heading.style.color = '#58a6ff';
          details.append(heading, textElement('p', 'Tarih: ' + s.date), textElement('p', 'ID: ' + s.id),
            textElement('p', 'Özet:'), textElement('p', s.snippet || 'Özet bulunmuyor.'), textElement('p', 'Anahtar Konular:'));
          const terms = document.createElement('div');
          Object.keys(s.terms || {}).slice(0, 8).forEach(term => {
            const badge = textElement('span', term);
            badge.className = 'badge';
            terms.appendChild(badge);
          });
          details.appendChild(terms);
        }
      }
    });

    // Arama filtreleme
    function applyFilters() {
      const q = document.getElementById('search').value.toLowerCase().trim();
      const maxDays = parseInt(document.getElementById('timeSlider').value);
      document.getElementById('daysVal').textContent = maxDays >= 180 ? 'Tümü' : maxDays + ' gün';
      nodes.forEach(node => {
        const full = rawSessions[node.id];
        const match = !q || full.title.toLowerCase().includes(q) || full.snippet.toLowerCase().includes(q);
        nodes.update({ id: node.id, hidden: !match || (maxDays < 180 && node.ageDays > maxDays) });
      });
    }
    document.getElementById('search').addEventListener('input', applyFilters);

    // Zaman filtresi
    document.getElementById('timeSlider').addEventListener('input', applyFilters);
  </script>
</body>
</html>
"""


def render_html(index_path: Path, output_html: Path) -> Path:
    """Sidecar index.json dosyasından interaktif HTML görselleştirmesi üretir."""
    if not index_path.exists():
        raise FileNotFoundError(f"Session Brain indeksi bulunamadı: {index_path}")

    if not path_within_vault(index_path, index_path.parent) or not path_within_vault(output_html, output_html.parent):
        raise ValueError("unsafe-session-viz-path")
    sessions = load_session_index(index_path)
    json_payload = json.dumps(sessions, ensure_ascii=False, allow_nan=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')

    html_content = HTML_TEMPLATE.replace("__SESSIONS_JSON__", json_payload)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(output_html, html_content.encode("utf-8"))
    return output_html
