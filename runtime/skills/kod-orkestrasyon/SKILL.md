---
name: kod-orkestrasyon
description: Çoklu AI model orkestrasyonu (Worktree izolasyonu). "orkestrasyon", "modeli işçi olarak çalıştır", "worktree'de dene" için kullan.
---

# Kod Orkestrasyonu (Any-to-Any Multi-AI Orchestrator)

Bu yetenek, ağır kodlama ve refactoring görevlerini ana depoyu riske atmadan izole bir Git worktree'sinde bir alt AI işçisine (Antigravity, Codex, Claude, Gemini) devretmeyi ve üretilen diff yamasını (`worker.patch`) ana depoya güvenle almayı sağlar.

## Temel Kurallar
1. **İzole Ağaç:** İşçi modeller ana depoya doğrudan dokunamaz. Her görev `../<repo>-worktrees/run-<id>` altında çalışır.
2. **Any-to-Any Serbestisi:** Master (Yönetici) ve Worker (İşçi) rolleri sabitleştirilemez. Kullanıcı veya herhangi bir model yönetici, diğeri işçi olabilir.
3. **Yama Paktı:** İşçi kodunu yazar, testleri koşturur ve `worker.patch` üretir. Master veya kullanıcı onaylamadan ana koda entegrasyon yapılmaz.

## Çalıştırma Komutları

```powershell
# Temel kullanım (İşçi: Antigravity)
python scripts/orchestrate.py --task "Görev tanımı" --master user --worker antigravity

# Yönetici Codex, İşçi Gemini (Doğrulama testiyle)
python scripts/orchestrate.py --task "Auth middleware refactoring" --master codex --worker gemini --test "pytest tests/auth_test.py"

# İşlem tamamlandığında worktree'yi temizle
python scripts/orchestrate.py --task "Fix typos" --master user --worker codex --cleanup
```

## Dashboard ve Web Arayüzü
Tüm aktif ve tamamlanan işçi koşuları `http://localhost:8520` (Gateway & Kontrol Paneli) üzerindeki **⚙️ Orkestrasyon** sekmesinde canlı olarak izlenebilir, üretilen diff görselleştirilebilir ve tek tıkla **✓ Onayla & Uygula** yapılabilir.
