
## PHASE 8: Verify and first-run report

```bash
ls -la "{{VAULT_PATH}}"
test -f "{{VAULT_PATH}}/CLAUDE.md" && echo "CLAUDE.md ✓"
test -f "{{VAULT_PATH}}/AGENTS.md" && echo "AGENTS.md ✓"
test -f "{{VAULT_PATH}}/.codex/hooks.json" && echo "Codex hooks ✓"
test -f "{{VAULT_PATH}}/.cursor/hooks.json" && echo "Cursor hooks ✓"
test -f "{{VAULT_PATH}}/.agents/hooks.json" && echo "Antigravity hooks ✓"
test -f "{{VAULT_PATH}}/.beyin/config.json" && echo "özetleyici ayarı ✓"
test -f "{{VAULT_PATH}}/🔮 850-Companion/Last-Session.md" && echo "hafıza ✓"
test -f "{{VAULT_PATH}}/.beyin-version" && echo "sürüm $(cat "{{VAULT_PATH}}/.beyin-version") ✓"
test -d "$HOME/Desktop/{{OS_NAME}}.app" && echo "launcher 🧠 ✓"
```

Then jump to **THE DEMO** at the bottom of this file.

---

# MODE B: Update an existing vault directly to Respected Brain

Use this mode for any existing vault created prior to the current `0.0.1` release.
Existing memory files are the whole point of the system; this update is strictly **additive and safe**:
- Personal notes and identity files (`🔮 850-Companion/Core.md`, `Journal.md`, `Threads.md`, `Last-Session.md`) are never overwritten.
- Managed runtime engines, hook adapters, skills, and templates are brought up to date atomically.
- Legacy version markers (`.beyin-version`, `.beyin-multi-version`) are cleanly consolidated into a single `.respectedbrain-version`.

## Preview first

```bash
python3 runtime/scripts/update_respected.py "/absolute/path/to/vault"
```

On native Windows:
```powershell
py -3 runtime/scripts/update_respected.py "$HOME\Documents\RespectedOS" --platform windows-native
```

This validates and prints managed paths without touching any file in the vault.

## Apply the update

```bash
python3 runtime/scripts/update_respected.py "/absolute/path/to/vault" --apply
```

(Optionally add `--force` to re-sync managed files even if already on `0.0.1`).

## The update guarantees

- **Atomic promotion:** Managed files stage outside the vault in a secure temporary directory.
- **External backup:** Target files are backed up to `~/.respected/update-backups/<vault-id>/<timestamp>/`.
- **Single version stamp:** Writes `.respectedbrain-version = 0.0.1` only after all integrity checks pass.
- **Clean migration:** If old version markers exist, they are safely retired.
- **No secret leaks:** Local credentials and untracked configs are preserved and kept out of version control.
- **Never destroy:** Personal notes, identity files, and custom notes are strictly preserved.
- **Idempotent:** Running `apply` multiple times is safe and skips already current components.

## PHASE U7: Optional global access

Follow PHASE 3B only if the user wants the same vault available automatically in unrelated code repositories.
Do **not**
run a second `enable_multiai.py` migration.

# THE DEMO (both modes end here)

Report in Turkish:

- ✅ **Ne kuruldu:** vault yolu ve kullanıcı seçtiği adı, hafıza motoru, `daily/`, `knowledge/`,
  canonical rules/skills, kurulan workspace adaptörleri ve varsa global provider bağlantıları.
- 🔁 **Agent değiştirme:** bir agentın tamamlanan turn özeti ortak vault'a yazıldıktan sonra diğer agent
  aynı bağlamı alır; sağlayıcının ham chat UI geçmişi taşınmaz.
- 🤖 **Özetleyici:** varsayılan `auto`; mevcut agent önce denenir, geçici limitte kurulu ve giriş
  yapılmış başka CLI'a fallback edilir. Kalıcı seçim yalnız kullanıcı isterse yapılır.
- ▶️ **İlk çalıştırma:** Obsidian'da `{{VAULT_PATH}}` klasörünü bir kez vault olarak aç. Sonra
  kullanıcının ana agentında kısa ama anlamlı bir test konuşması başlat.

## Prove one real lifecycle

Do not require session close. Send one harmless but meaningful prompt, wait for the provider's
completed-turn hook, then poll for the daily log:

```bash
BEYIN_LOG="{{VAULT_PATH}}/daily/$(date +%F).md"
BEYIN_TRY=0
BEYIN_OK=0
while [ "$BEYIN_TRY" -lt 24 ]; do
  if [ -f "$BEYIN_LOG" ] && grep -q '^### Oturum' "$BEYIN_LOG" 2>/dev/null; then
    BEYIN_OK=1
    break
  fi
  BEYIN_TRY=$((BEYIN_TRY + 1))
  sleep 5
done
if [ "$BEYIN_OK" = "1" ]; then
  echo "GUNLUK LOG HAZIR: $BEYIN_LOG"
  tail -12 "$BEYIN_LOG"
else
  echo "GUNLUK LOG 120 SANIYEDE YAZILMADI: $BEYIN_LOG"
fi
```

- `GUNLUK LOG HAZIR`: show the tail. Then open a **different installed agent** and confirm its
  first context contains the last session/topic. This proves cross-agent continuity, not merely
  same-agent memory.
- `GUNLUK LOG 120 SANIYEDE YAZILMADI`: run `beyin doktor`. Check that the session was long enough,
  hook trust is granted, `python3` exists, and at least one local AI CLI is authenticated.

## Honest timing and quota behavior

- **Daily log:** starts at a supported native completed-turn event and normally takes seconds;
  session-end/pre-compact are catch-up paths.
- **Knowledge compile:** runs in the morning pipeline before the 08:00 briefing and catches up
  completed earlier days on session start without ingesting today's partial log. It runs completely
  headless and quiet in the background without opening UI windows.
- **Quota:** usage belongs to whichever CLI actually answered. Retryable limit/timeout/5xx errors
  fall through to another installed CLI. Authentication/configuration failures stop visibly.

Do not end with only "kuruldu". Report the tested provider, whether fallback alternatives are
actually installed/authenticated, the global backup path, and any one-time action still needed
(for example Codex `/hooks` trust or restarting an IDE to reload user hooks).

Done. The user now has one portable memory layer instead of five disconnected agent memories.
