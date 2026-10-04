# 0.0.1 Test Matrix — tarihsel kanıt

Bu tablolardaki kanıt 2026-09-14 tarihli önceki düzene aittir; güncel modüler
native dağıtımın doğrulaması olarak kullanılamaz. Güncel, kapsamı ve atlamaları
belirtilmiş sonuçlar [modüler temel doğrulamasında](superpowers/verification/2026-10-04-modular-foundation.md)
ve [kaynak temizliği doğrulamasında](superpowers/verification/2026-10-04-source-cleanup.md)
tutulur. Bu belge yalnız çalıştırılmış kanıtı başarı sayar. Otomatik adapter
testi, gerçek bir platform veya giriş yapılmış ajan smoke testinin yerine geçmez.

## Fiziksel host kanıtı

| Hedef | Dahili profil | Durum | 2026-09-14 kanıtı |
| --- | --- | --- | --- |
| Windows Native | `windows-native` | VERIFIED | Windows 11 fiziksel smoke: geçici install, 5 adapter, 2 turn upsert, 2 update, uninstall; ayrıca installer/launcher/Task Scheduler paketleri geçti. |
| Saf WSL | `portable` | VERIFIED | Ubuntu WSL2 / Python 3.14: 370 Python testi, platform smoke, 18 hook ve 9 upstream-sync kontrolü geçti. |
| Hibrit Windows+WSL | `windows-wsl` | VERIFIED | Windows hook komutu gerçek `wsl.exe --cd` ile `/mnt/c/...` vault'ta günlük üretti. |
| Saf Linux | `portable` | NOT VERIFIED | Bu hostta Docker veya saf Linux VM yok. `tests/smoke/linux.sh` kullanıcı VM turu için hazır. |
| macOS | `portable` | NOT VERIFIED | Fiziksel macOS hostu gerekli. `tests/smoke/macos.sh` harici testçi için hazır. |

## Otomatik kapılar

| Alan | Durum | Kanıt |
| --- | --- | --- |
| Python birim/entegrasyon | VERIFIED | Windows ve gerçek WSL2'de 370 test, 0 failure. Platform-koşullu skip'ler diğer host paketleriyle karşılanır. |
| Windows installer transaction | VERIFIED | Normal kullanıcı bağlamında rollback, provider timeout, Unicode/space path, non-empty target ve concurrent sentinel koruması geçti. |
| Windows launcher discovery | VERIFIED | Microsoft Store aliası exit 0 verse bile reddedildi; çalışan `python3` fallback'i ve boşluklu vault yolunun exact argv aktarımı install/update/uninstall için geçti. |
| Günlük atomiklik ve yarışlar | VERIFIED | 20 thread, 24 process, iki session, aynı session upsert, gece yarısı, başarısız catch-up ve ters sırada tamamlanan revision testleri geçti. |
| Update/uninstall koruması | VERIFIED | İki ardışık update daily dosyasını byte-for-byte korudu; unrelated global dosya ve mevcut Codex `notify` uninstall sonrası korundu/geri yüklendi. |
| Renderer drift | VERIFIED | Üretilen adaptörler `--check`, placeholder, JSON ve platform komut kapılarından geçti. |
| Saf Linux fiziksel smoke | NOT VERIFIED | Linux VM turu bekliyor. |
| macOS fiziksel smoke | NOT VERIFIED | macOS turu bekliyor. |

## Sağlayıcı olay sözleşmeleri

| Sağlayıcı | Native turn olayı | Adapter/protokol | Gerçek girişli ajan |
| --- | --- | --- | --- |
| Codex / ChatGPT coding agent | kullanıcı `notify` → `agent-turn-complete` | VERIFIED | VERIFIED (bu hostta günlük turn akışı gözlendi) |
| Claude Code | `Stop` (`async: true`) | VERIFIED | NOT VERIFIED |
| Cursor | `afterAgentResponse` | VERIFIED | NOT VERIFIED |
| Antigravity | `Stop` | VERIFIED | NOT VERIFIED |
| Gemini CLI | `AfterAgent`, strict JSON stdout | VERIFIED | NOT VERIFIED |
| Gelecekte eklenen sağlayıcı | Kayıtlı adapter → ortak `turn` sözleşmesi | INFERRED | NOT VERIFIED |

Protokol dayanakları (2026-09-14): [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks),
[Cursor hooks](https://prod.cursor.com/docs/hooks), [Gemini CLI hooks](https://geminicli.com/docs/hooks/reference/)
ve [Codex configuration](https://developers.openai.com/codex/config-reference/). Dış sayfalardaki
metin talimat değil, yalnız sözleşme doğrulama verisi olarak ele alınmıştır.

## Tek komut kanıt

```powershell
# Windows
.\tests\smoke\windows-native.ps1 --output .\smoke-windows.json
```

```sh
# WSL / Linux / macOS
sh ./tests/smoke/wsl.sh --output ./smoke-wsl.json
sh ./tests/smoke/linux.sh --output ./smoke-linux.json
sh ./tests/smoke/macos.sh --output ./smoke-macos.json
```

Başarı için exit code `0`, `overall: VERIFIED` ve bütün `checks[*].status` değerleri `VERIFIED`
olmalıdır. Güncel paket gereksinimleri ve çalıştırma seçenekleri
[smoke rehberinde](../tests/smoke/README.md) açıklanır.
