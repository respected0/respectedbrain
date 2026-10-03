---
name: obsidian-layout
description: Obsidian görsel temasını ve CSS snippetlarını düzenler. "obsidian tema", "css düzenle", "görünüm" için kullan.
---

# Obsidian Görsel Düzenleyici (Layout Adjustment)

Bu skill, Obsidian arayüzünü kullanıcının isteğine göre CSS snippet'ları üzerinden güvenle düzenler.

## Nasıl Çalışırsın
1. Temel sistem CSS dosyası `.obsidian/snippets/secondbrain-layout.css` dosyasında yaşar ve sistem güncellemeleriyle senkronize edilir.
2. Kullanıcıya özel stil/renk değişiklikleri gerekiyorsa, sistem güncellemelerinde ezilmemesi için `.obsidian/snippets/custom.css` dosyasına yazılır.
3. Obsidian'da snippet'ları aktif etmek için `.obsidian/appearance.json` içindeki `enabledCssSnippets` listesine snippet adı eklenir.
4. Asla temayı bozacak global `!important` karmaşası yaratma, CSS değişkenlerini (`var(--interactive-accent)`, `var(--background-primary)`) kullan.

## Temel Sınıflar
- `.nav-file-title`, `.nav-folder-title`: Dosya ağacı satırları ve klasör başlıkları.
- `.workspace-tab-header`: Açık sekme başlıkları.
- `.metadata-container`: Not başındaki Properties (frontmatter) kartı.
- `.callout`: `> [!NOTE]` vb. çağrı blokları.
- `a.internal-link`: `[[wikilink]]` bağlantıları.
- `.graph-view-container`: Graf görünüm penceresi.
