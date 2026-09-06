---
name: obsidian-layout
description: Obsidian görsel arayüzünü, sekmeleri, dosya ağacını, fontları ve CSS snippet'larını düzenler. "obsidian tema", "obsidian görünüm", "css düzenle", "sekmeler", "arayüz" dendiğinde kullan.
---

# Obsidian Görsel Düzenleyici (Layout Adjustment)

Bu skill, Obsidian arayüzünü kullanıcının isteğine göre CSS snippet'ları üzerinden güvenle düzenler.

## Nasıl Çalışırsın
1. CSS dosyaları `.obsidian/snippets/` klasöründe yaşar (`secondbrain-layout.css`).
2. Obsidian'da snippet'ı aktif etmek için `.obsidian/app.json` veya `appearance.json` içindeki `enabledCssSnippets` listesine snippet adı eklenir.
3. Asla temayı bozacak global `!important` karmaşası yaratma, CSS değişkenlerini (`var(--interactive-accent)`, `var(--background-primary)`) kullan.

## Temel Sınıflar
- `.nav-file-title`, `.nav-folder-title`: Dosya ağacı satırları ve klasör başlıkları.
- `.workspace-tab-header`: Açık sekme başlıkları.
- `.metadata-container`: Not başındaki Properties (frontmatter) kartı.
- `.callout`: `> [!NOTE]` vb. çağrı blokları.
- `a.internal-link`: `[[wikilink]]` bağlantıları.
- `.graph-view-container`: Graf görünüm penceresi.
