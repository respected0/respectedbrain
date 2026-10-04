---
name: ajan-gecmis-tara
description: Yerel AI ajan (Antigravity, Codex) loglarını tarar. "ajan geçmiş", "geçmiş tara" dendiğinde kullan.
---

# Çapraz Ajan Geçmiş Madencisi (/ajan-gecmis-tara)

Native örneklerde `UUID` değerini `respectedbrain vault list` çıktısındaki kayıtlı kasa
kimliğiyle değiştir. Not yolları VaultRoot'a göre çözülür; teknik state/cache DataRoot içinde
UUID bazında tutulur. Kurulu launcher ayrıca Python veya kaynak checkout gerektirmez.

## Amaç ve İlke

Kullanıcı farklı projelerde çalışırken Claude Code, Antigravity veya Codex ile derin teknik problemler çözmüş olabilir. Bu oturumların hepsi yerel diskte JSONL formatında durur. Bu beceri, harici bir dışa aktarma zip'i beklemeden doğrudan diskteki ajan klasörlerini tarar, konuşmaları imbikten geçirir ve ikinci beyin vault'una aktarır.

## Desteklenen Ajanlar

- **Google Antigravity:** `%USERPROFILE%\.gemini\antigravity-ide\brain\*\transcript.jsonl`
- **Claude Code:** `~/.claude/projects/` altındaki JSONL oturumları
- **OpenAI Codex:** `~/.codex/sessions/*.jsonl`

## Akış

1. **Önizleme (Dry-run):**
   Önce diski tara ve kaç adet yeni oturum bulunduğunu göster:
   ```bash
   respectedbrain maintenance --vault-id UUID mine_agent_history --dry-run --limit 10
   ```

2. **Kullanıcı Onayı:**
   Hangi ajanların (hepsi, yalnız antigravity, yalnız claude veya yalnız codex) ve nereye (`daily/` veya `📥 000-Inbox/Dump/`) aktarılacağını teyit et.

3. **İçe Aktarma (Import):**
   Onaylanan oturumları vault'a aktar:
   ```bash
   respectedbrain maintenance --vault-id UUID mine_agent_history --source all --limit 10 --target daily
   ```

4. **Derleme ve Haritalama:**
   Aktarılan logları derleyiciye bildirmek veya haritayı güncellemek için:
   ```bash
   respectedbrain search --vault-id UUID --reindex
   ```
