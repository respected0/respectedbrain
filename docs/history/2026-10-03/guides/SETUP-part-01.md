> Tarihsel kayıt (2026-10-03). Önceki düzenin tam metnidir; güncel kurulum talimatı değildir. [Güncel rehber](../../../../README.md), [sözleşme](../../../../docs/superpowers/specs/2026-10-03-modular-foundation-design.md).

# SETUP.md multi-AI: Activate this second brain (agent runbook)

> Respected Brain Claude Code, Codex, Cursor, Antigravity ve Gemini CLI ile kullanılabilir. Kurulum sonunda
> `python3 runtime/scripts/render_integrations.py` çalıştır. Mevcut bir Respected Brain vault'unu güncellemek
> için `runtime/scripts/update_respected.py` (veya `python installer/update.py`) kullan; eksik multi-AI katmanını tamamlamak için `enable_multiai.py`
> kullanılır. Ayrıntı: `MULTI_AI.md`.

## Platform profiles

Respected has exactly three installed runtime profiles:

| Profile | Runtime command | Use when |
| --- | --- | --- |
| `portable` | `python3` | macOS or Linux |
| `windows-wsl` | `wsl.exe --cd <vault> python3` | Windows IDE + WSL runtime |
| `windows-native` | kurulumda doğrulanan mutlak Python 3 executable | Windows without WSL/Bash |

If this checkout is running directly in Windows and the user wants a fresh native vault, stop this
POSIX-oriented runbook and follow `SETUP-WINDOWS.md`. 0.0.1 öncesi veya önceki sürümlerden kalan mevcut bir vault için,
`runtime/scripts/update_respected.py --platform windows-native` (veya `python installer/update.py`) desteklenir.
Claude is never mandatory when another selected provider CLI is installed and authenticated.

> You are a coding agent, run from inside a freshly cloned `respectedbrain` repo. The user wants their
> own AI second brain, or wants to upgrade the one they already have. The scaffold lives in
> `./template/`. Your job: decide the mode, interview the user, install or upgrade, verify.
> Execute phase by phase. Speak **Turkish** to the user (the audience is Turkish). This runbook is
> in English only so your instructions stay precise; the system you build talks Turkish.

## Rules (binding)

1. **Interview first, build second.** Nothing touches the filesystem before PHASE 0.
2. **Never destroy.** If a target file or folder exists, show it and ask. Default to merge or
   skip, never a silent clobber. In upgrade mode this is absolute: existing memory files are
   read-only for you.
3. **Resolve every `{{PLACEHOLDER}}`.** Never leave a literal `{{...}}` in any written file.
4. **Don't block on optional steps** (obsidian-cli, mem0, swift icon). Log it, tell the user,
   continue.
5. **Verify each phase** with a quick check before moving on. End with the first-run report.
6. **Be the demo.** This is often filmed. Narrate what you are doing in short Turkish lines as you
   go: "Vault iskeletini kuruyorum...", "Hafıza motorunu bağlıyorum...", "Derleyiciyi yerine
   koyuyorum...". Short sentences, no walls of text.
7. **No extra API key is required.** The background summarizer and compiler use an authenticated
   local CLI (`claude`, `codex`, `agy`, `gemini`, or `cursor-agent`) and consume that provider's existing
   subscription/quota.
8. **Do not force one provider.** Default the summary provider to `auto`. Only persist a specific
   provider when the user explicitly asks. Switching the coding agent must not require migration.

Placeholders you must resolve:
`{{OS_NAME}}` · `{{USER_NAME}}` · `{{USER_BIO}}` · `{{COMPANION}}` · `{{VAULT_PATH}}` ·
`{{SCOPE}}` · `{{USE_MEM0}}` · `{{TODAY}}`

| Placeholder | Nereden gelir | Örnek |
| --- | --- | --- |
| `{{OS_NAME}}` | makine adından türetilir, kullanıcı onaylar | `AylinOS` |
| `{{USER_NAME}}` | soru 1 | `Aylin` |
| `{{USER_BIO}}` | soru 2, 1 veya 2 cümle | `Ürün tasarımcısı, yan projeler yürütüyor` |
| `{{COMPANION}}` | soru 3, AI ortağının adı | `Echo` |
| `{{VAULT_PATH}}` | PHASE 0.3 | `~/Documents/AylinOS` |
| `{{SCOPE}}` | soru 4, opsiyonel klasörler | `core+goals` |
| `{{USE_MEM0}}` | soru 5 | `evet` |
| `{{TODAY}}` | `date +%F` | `2026-08-22` |

`{{SCOPE}}` ve `{{USE_MEM0}}` dosya içine yazılmaz, sadece hangi klasörlerin ve hangi opsiyonel
adımın çalışacağını belirler. Diğer altısı dosya içeriklerinde geçer.

---

## PHASE M: Mode selection (do this FIRST, before anything else)

Ask the user in Turkish: **"Daha önce kurulmuş bir beynin var mı? Varsa klasör yolunu ver."**
If they say no, still scan the two default locations before deciding:

No globs here. An empty `Documents` folder makes `"$HOME/Documents"/*` abort the whole command under
zsh with `no matches found`, and the setup agent may be running either bash or zsh. `find` cannot
do that.

```bash
BEYIN_LIST=$(mktemp)
for BEYIN_BASE in "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents" "$HOME/Documents"; do
  [ -d "$BEYIN_BASE" ] || continue
  find "$BEYIN_BASE" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null >> "$BEYIN_LIST"
done
BEYIN_HITS=0
while IFS= read -r BEYIN_D; do
  [ -f "$BEYIN_D/CLAUDE.md" ] || continue
  BEYIN_MEM=$(find "$BEYIN_D" -mindepth 1 -maxdepth 1 -type d -name "🔮 850-*" -print 2>/dev/null | head -1)
  [ -n "$BEYIN_MEM" ] || continue
  BEYIN_HITS=$((BEYIN_HITS + 1))
  echo "ADAY: $BEYIN_D"
  echo "  hafıza klasörü: $(basename "$BEYIN_MEM")"
  if [ -f "$BEYIN_D/.respectedbrain-version" ]; then
    echo "  sürüm: $(sed -n '1p' "$BEYIN_D/.respectedbrain-version")"
  else
    echo "  sürüm: 0.0.1 öncesi (eski sürüm)"
  fi
done < "$BEYIN_LIST"
rm -f "$BEYIN_LIST"
echo "TARAMA TAMAM: $BEYIN_HITS aday bulundu"
```

The last line is the success check. If you do not see `TARAMA TAMAM`, the scan did not finish and
you may not pick a mode yet: fix the error first.

Decide:

| Bulgu | Mod |
| --- | --- |
| `TARAMA TAMAM: 0 aday` | **MODE A, sıfırdan kurulum** (PHASE 0'a git) |
| Aday var, sürüm `0.0.1` öncesi | **MODE C, güncelleme**: `runtime/scripts/update_respected.py` ile `0.0.1` sürümüne güncelle |
| Aday var, sürüm `0.0.1` | Zaten güncel Respected Brain. `beyin-doktor` çalıştır (gerekirse `--force`) |
| Aday var, bilinmeyen durum | Kullanıcıya göster, ne yapılacağını sor |

Tell the user which mode you picked and why, in one Turkish sentence. Never guess silently.

---

# MODE A: Fresh install

## PHASE 0: Interview

Detect the machine name and derive the OS name:

```bash
scutil --get ComputerName 2>/dev/null || hostname
```

PascalCase it and append `OS` (strip "MacBook/Pro/Air/iMac/'s", apostrophes, dashes).
`Johns-MacBook-Pro` → `JohnOS`, `aylin's Mac` → `AylinOS`, `DESKTOP-AB12` → `Ab12OS`.
Propose `{{OS_NAME}}`, let the user override.

Ask (Turkish, conversational, not a form):

1. **İsmin ne?** → `{{USER_NAME}}`
2. **Ne iş yapıyorsun, bu beyni en çok ne için kullanacaksın?** → `{{USER_BIO}}`
3. **AI ortağına ne isim vermek istersin?** → `{{COMPANION}}`
4. **Kapsam:** core (herkes) + opsiyonel `⚔️ 200-Goals`, `🔐 400-Vault`, `💪 700-Body`,
   `🧘 800-Mind` → `{{SCOPE}}`
5. **Semantik hafıza (mem0)?** Temel sürümü **ücretsiz** (mem0.ai, kredi kartı yok). Dosya
   tabanlı hafıza onsuz da tam çalışır, mem0 üstüne anlamsal arama katar. Önerilir. →
   `{{USE_MEM0}}`
6. **Hangi agentları kullanıyorsun?** Claude Code, Codex, Cursor, Antigravity, Gemini arasından seçtir.
   Birden fazla seçim normaldir. Bu değer global kurulumun `--providers` listesidir.
7. **Her kod reposunda aynı beyin otomatik açılsın mı?** Evet önerilir. Evetse kullanıcı düzeyi
   global bağlantıyı PHASE 3B'de önizle, açık onaydan sonra uygula.

Pick the vault path → `{{VAULT_PATH}}`:

- If `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/` exists → `.../Documents/{{OS_NAME}}`
- Else → `~/Documents/{{OS_NAME}}`

Confirm the path with the user. Set `{{TODAY}}` = `date +%F`.

## PHASE 1: Prerequisites

Branch on the platform first. macOS is the tested path. The Linux path exists but has not been
verified on a real Linux desktop; say so to the user instead of pretending.

```bash
BEYIN_PLATFORM=$(uname -s)
echo "platform: $BEYIN_PLATFORM"
if [ "$BEYIN_PLATFORM" = "Darwin" ]; then
  if ! command -v brew >/dev/null 2>&1; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # The Homebrew installer only PRINTS the shellenv lines, it never applies them to this shell.
    # Without this loop the very next `brew` call fails on a fresh Apple Silicon Mac.
    for BEYIN_BREW in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      [ -x "$BEYIN_BREW" ] || continue
      eval "$("$BEYIN_BREW" shellenv)"
      break
    done
  fi
  if command -v brew >/dev/null 2>&1; then
    echo "brew ✓ $(command -v brew)"
    [ -d "/Applications/Obsidian.app" ] || brew install --cask obsidian
    command -v obsidian >/dev/null 2>&1 \
      || (brew tap yakitrak/yakitrak >/dev/null 2>&1 && brew install yakitrak/yakitrak/obsidian-cli >/dev/null 2>&1) \
      || echo "obsidian-cli atlandı (opsiyonel)"
  else
    echo "🔴 BREW YOK: Homebrew kurulumu tamamlanmadı. Obsidian'ı elle kur: https://obsidian.md/download"
  fi
  [ -d "/Applications/Obsidian.app" ] && echo "Obsidian ✓" || echo "🟡 Obsidian bulunamadı, elle kurulmalı"
else
  # Linux / other. No Homebrew, no cask, no .app bundle. NOT verified on a real Linux desktop.
  echo "macOS değil. Homebrew, Obsidian cask ve macOS masaüstü uygulaması adımları atlanıyor."
  echo "Obsidian'ı dağıtımının paket yöneticisinden veya https://obsidian.md/download üstünden kur."
  command -v obsidian >/dev/null 2>&1 && echo "obsidian-cli ✓" || echo "obsidian-cli yok (opsiyonel)"
fi
```

**Hard requirement:** `python3` and at least one supported authenticated local AI CLI must be
present. Claude is not mandatory.

```bash
BEYIN_MISSING=0
if command -v python3 >/dev/null 2>&1; then
  echo "python3 ✓ $(python3 -V 2>&1)"
else
  echo "🔴 python3 YOK"
  BEYIN_MISSING=$((BEYIN_MISSING + 1))
fi
BEYIN_CLI_COUNT=0
for BEYIN_CLI in claude codex agy gemini cursor-agent; do
  if command -v "$BEYIN_CLI" >/dev/null 2>&1; then
    echo "$BEYIN_CLI CLI ✓ $(command -v "$BEYIN_CLI")"
    BEYIN_CLI_COUNT=$((BEYIN_CLI_COUNT + 1))
  fi
done
if [ "$BEYIN_CLI_COUNT" -eq 0 ]; then
  echo "🔴 DESTEKLENEN AI CLI YOK: claude | codex | agy | gemini | cursor-agent"
  BEYIN_MISSING=$((BEYIN_MISSING + 1))
fi
echo "ONKOSUL SONUC: $BEYIN_MISSING eksik"
```

`ONKOSUL SONUC: 0` is the only line that lets you continue. `python3` is what the background
summarizer and the compiler run on, and it is the entire architecture thesis. If it is missing:

- macOS: `xcode-select --install`, then run the block again.
- Linux: install `python3` with your package manager, then run the block again.

Do not carry on quietly. If the user insists on continuing without python3, say in Turkish that
this is a **degraded kurulum**: continuity works, the automatic daily log and the knowledge
compilation stay off. Then repeat that sentence in the final report and never call the install
successful. `beyin doktor` will show it red every single time until python3 exists.

## PHASE 2: Place the vault

```bash
mkdir -p "$(dirname "{{VAULT_PATH}}")"
cp -R "./template/" "{{VAULT_PATH}}/"
find "{{VAULT_PATH}}/.claude/hooks" -maxdepth 1 -type f -name "*.sh" -exec chmod +x {} +
find "{{VAULT_PATH}}/.claude/hooks" -maxdepth 1 -type f -name "*.sh" -exec bash -n {} \; \
  && echo "KANCA SOZDIZIMI: tamam"
```

No globs in the chmod. Under zsh an unmatched `*.sh` aborts the whole command with
`no matches found`, and you do not know which shell you are running in.

Create only the optional scope folders the user picked in `{{SCOPE}}`:
`⚔️ 200-Goals` · `🔐 400-Vault` · `💪 700-Body` · `🧘 800-Mind`

Verify the runtime pieces landed:

```bash
cd "{{VAULT_PATH}}"
ls .claude/hooks/             # session-start.sh prompt-counter.sh session-end.sh pre-compact.sh lib.sh
ls .beyin/engine/             # flush.py compile.py
ls .claude/skills/            # beyin-doktor gecmis-import
ls -d daily knowledge/concepts knowledge/connections
cat .respectedbrain-version   # 0.0.1
```

## PHASE 3: Personalize (substitute placeholders)

Replace EVERY placeholder in EVERY file under `{{VAULT_PATH}}` with the resolved values, then
verify none remain:

```bash
grep -rl "{{" "{{VAULT_PATH}}" || echo "✓ tüm placeholder'lar dolduruldu"
```

Also update the structure section of `.beyin/instructions.md` to list optional scope folders, then
regenerate the provider adapters:

```bash
cd "{{VAULT_PATH}}"
python3 scripts/render_integrations.py --root .
python3 scripts/render_integrations.py --root . --check
```

Do not edit generated `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/beyin.mdc`, or
`.agents/rules/beyin.md` independently.
The memory folder stays `🔮 850-Companion` even when the companion has a name: the hooks and the
scripts reference that fixed path. The persona name lives in the file *contents*, not in the
folder name. Say this to the user in one line so it does not look like a bug.

## PHASE 3B: Optional global multi-agent connection

If the user answered yes to global connection, run a preview first. `{{PROVIDERS}}` is `all` or a
comma-separated subset such as `antigravity,codex`. The vault name is arbitrary.

Portable macOS/Linux:

```bash
python3 "{{VAULT_PATH}}/scripts/install_global.py" "{{VAULT_PATH}}" \
  --home "$HOME" --platform portable --providers "{{PROVIDERS}}"
```

Windows applications with a WSL vault use the Windows user root visible under `/mnt`, for example:

```bash
python3 "{{VAULT_PATH}}/scripts/install_global.py" "{{VAULT_PATH}}" \
  --home "/mnt/c/Users/<windows-user>" --platform windows-wsl --providers "{{PROVIDERS}}"
```

If Antigravity IDE will also use **Connect to WSL**, append the explicit Linux profile root:

```bash
python3 "{{VAULT_PATH}}/scripts/install_global.py" "{{VAULT_PATH}}" \
  --home "/mnt/c/Users/<windows-user>" \
  --antigravity-home "/home/<wsl-user>" \
  --platform windows-wsl --providers "{{PROVIDERS}}"
```

The repeatable `--antigravity-home` option installs only Antigravity's `.gemini` integration in
those additional roots. Do not infer or scan profiles; ask for each root explicitly. Omit the
option when Connect to WSL is not used.

Show the listed files. Only after approval, repeat the exact command with `--apply`. The installer
merges existing user rules/hooks, takes a backup, installs global skills, and avoids double-running
when the vault itself is the active workspace. Leave `.beyin/config.json` at
`{"summary_provider":"auto"}` unless the user explicitly chooses another provider; if they do:

```bash
cd "{{VAULT_PATH}}" && python3 scripts/set_summary_provider.py <provider>
```

## PHASE 3C: Optional 08:00 morning briefing schedule

Explain that the worker is provider-neutral, produces at most one successful briefing per day and
that schedule installation changes user-level operating-system configuration. Preview first and
show the complete definition, command and target paths; run the same command with `--apply` only
after explicit approval. Replaced managed definitions are backed up under
`~/.respected/schedule-backups/` and restored if activation fails.

```bash
# Linux
python3 "{{VAULT_PATH}}/scripts/install_briefing_schedule.py" "{{VAULT_PATH}}" \
  --home "$HOME" --platform linux

# macOS
python3 "{{VAULT_PATH}}/scripts/install_briefing_schedule.py" "{{VAULT_PATH}}" \
  --home "$HOME" --platform macos

# Windows + WSL
python3 "{{VAULT_PATH}}/scripts/install_briefing_schedule.py" "{{VAULT_PATH}}" \
  --home "/mnt/c/Users/<windows-user>" --platform windows-wsl
```

Windows native uses the equivalent command from `SETUP-WINDOWS.md`. Declining this step leaves the
worker available for manual use and does not install a task.

## PHASE 4: Git

The vault is the user's memory. Version it from day one, so an upgrade or a bad edit is always
reversible.

```bash
cd "{{VAULT_PATH}}"
git init -q 2>/dev/null || true
git add -A
BEYIN_LEAK=$(git diff --cached --name-only | grep -E 'settings\.local\.json|\.yedek|\.bak$|(^|/)\.env$' || true)
if [ -n "$BEYIN_LEAK" ]; then
  git reset -q
  echo "🔴 SAHNELENMESI YASAK DOSYA: $BEYIN_LEAK"
  echo "   .gitignore eksik. Once onu duzelt, sonra tekrar dene."
  exit 1
fi
BEYIN_STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
BEYIN_NAME=$(git config user.name  2>/dev/null || echo "")
BEYIN_MAIL=$(git config user.email 2>/dev/null || echo "")
[ -n "$BEYIN_NAME" ] || BEYIN_NAME="{{USER_NAME}}"
[ -n "$BEYIN_MAIL" ] || BEYIN_MAIL="beyin@localhost"
if [ "$BEYIN_STAGED" -gt 0 ]; then
  if git -c user.name="$BEYIN_NAME" -c user.email="$BEYIN_MAIL" \
       commit -q -m "{{OS_NAME}}: ikinci beyin kuruldu"; then
    echo "ILK COMMIT: $(git rev-parse --short HEAD) ($BEYIN_STAGED dosya)"
  else
    echo "🔴 ILK COMMIT BASARISIZ: $BEYIN_STAGED dosya sahnede kaldı"
  fi
else
  echo "🔴 SAHNEDE DOSYA YOK: kopyalama adımı çalışmamış olabilir"
fi
```

Always pass `-c user.name` and `-c user.email`, falling back to the user's own global identity
when it exists. Without them, a machine with no git identity fails the commit and the old
`|| echo "commit atlandı"` line turns that failure into a success-looking message while every
file stays staged. Do not create any remote, do not push anywhere. This repo is local and private
by default.

## PHASE 5: Desktop launcher (brain icon 🧠)

Platform split. The macOS branch is the one that has been used and filmed. The Linux branch writes
a standard XDG desktop entry and is **untested on a real Linux desktop**; tell the user that.

```bash
if [ "$(uname -s)" = "Darwin" ]; then
  # 1) launcher applet
  osacompile -o "$HOME/Desktop/{{OS_NAME}}.app" \
    -e 'do shell script "open \"obsidian://open?vault={{OS_NAME}}\""'

  # 2) render 🧠 to PNG (Swift + AppKit, present on every Mac with Command Line Tools)
  cat > /tmp/render_brain.swift <<'SWIFT'
import AppKit
let out = CommandLine.arguments[1]; let size = 1024.0
let img = NSImage(size: NSSize(width: size, height: size)); img.lockFocus()
let pt = size * 0.78
let font = NSFont(name: "Apple Color Emoji", size: pt) ?? NSFont.systemFont(ofSize: pt)
let s = "🧠" as NSString; let b = s.size(withAttributes: [.font: font])
s.draw(at: NSPoint(x: (size-b.width)/2, y: (size-b.height)/2), withAttributes: [.font: font])
img.unlockFocus()
if let t = img.tiffRepresentation, let r = NSBitmapImageRep(data: t),
   let p = r.representation(using: .png, properties: [:]) { try? p.write(to: URL(fileURLWithPath: out)) }
SWIFT
  command -v swift >/dev/null 2>&1 && swift /tmp/render_brain.swift /tmp/brain.png || echo "swift yok, ikon atlandı"

  # 3) set as app icon (writes the custom Icon resource, overrides the default applet icon)
  cat > /tmp/set_icon.swift <<'SWIFT'
import AppKit
let img = NSImage(contentsOfFile: CommandLine.arguments[1])!
print(NSWorkspace.shared.setIcon(img, forFile: CommandLine.arguments[2], options: []) ? "icon ✓" : "icon FAILED")
SWIFT
  if command -v swift >/dev/null 2>&1 && [ -f /tmp/brain.png ]; then
    swift /tmp/set_icon.swift /tmp/brain.png "$HOME/Desktop/{{OS_NAME}}.app"
  fi

  # 4) refresh Finder
  touch "$HOME/Desktop/{{OS_NAME}}.app"
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$HOME/Desktop/{{OS_NAME}}.app" 2>/dev/null || true
  [ -d "$HOME/Desktop/{{OS_NAME}}.app" ] && echo "BASLATICI: macOS .app hazır" || echo "BASLATICI: kurulamadı"
else
  # Linux: XDG desktop entry. No osacompile, no AppKit, no .app bundle.
  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/{{OS_NAME}}.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name={{OS_NAME}}
Comment=Ikinci beyin vault
Exec=xdg-open "obsidian://open?vault={{OS_NAME}}"
Icon=obsidian
Terminal=false
Categories=Utility;
DESKTOP
  chmod +x "$HOME/.local/share/applications/{{OS_NAME}}.desktop"
  command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  [ -f "$HOME/.local/share/applications/{{OS_NAME}}.desktop" ] \
    && echo "BASLATICI: Linux .desktop yazıldı (gerçek bir Linux masaüstünde doğrulanmadı)" \
    || echo "BASLATICI: kurulamadı"
fi
```

The launcher only works after the vault has been added to Obsidian once (PHASE 8). On Linux, say
in one Turkish line that this shortcut has not been tested on a real Linux desktop and that opening
the folder in Obsidian by hand always works.

## PHASE 6: mem0 semantic memory (optional, FREE, only if `{{USE_MEM0}}` is yes)

1. `command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Free API key from https://mem0.ai, stored in `{{VAULT_PATH}}/.claude/settings.local.json`:
   `{ "env": { "MEM0_API_KEY": "..." } }`. That file is already gitignored. Never commit it.
3. Tell the user it is an upgrade layer. The file-based memory and the whole pipeline work
   without it, with no key at all.

## PHASE 7: First doctor run

Ask the agent performing setup to run the `beyin-doktor` skill against `{{VAULT_PATH}}`. The
canonical skill is rendered for every supported agent; Claude is not required. Close every 🔴 row
before you report success.
If the doctor cannot run for any reason, do the manual check instead:

```bash
cd "{{VAULT_PATH}}"
ls -l .claude/hooks/*.sh | awk '{print $1, $NF}'   # hepsi çalıştırılabilir olmalı
python3 -c "import json;d=json.load(open('.claude/settings.json'));print(sorted(d.get('hooks',{})))"
python3 -m py_compile .beyin/engine/flush.py .beyin/engine/compile.py && echo "scriptler ✓"
```
