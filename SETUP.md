# SETUP.md multi-AI: Activate this second brain (agent runbook)

> Bu fork Claude Code, Codex, Cursor ve Antigravity ile kullanılabilir. Kurulum sonunda
> `python3 scripts/render_integrations.py` çalıştır. Mevcut v1 vault'u doğrudan Respot Brain'e
> yükseltmek için `scripts/upgrade.sh` akışını kullan; bağımsız `enable_multiai.py` yalnız zaten
> v2 olan eski/harici kurulumları elle tamamlama ve onarım aracıdır. Ayrıntı:
> `MULTI_AI.md`.

> You are a coding agent, run from inside a freshly cloned `respot-brain` repo. The user wants their
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
   local CLI (`claude`, `codex`, `agy`, or `cursor-agent`) and consume that provider's existing
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
  if [ -f "$BEYIN_D/.beyin-version" ]; then
    echo "  sürüm: $(sed -n '1p' "$BEYIN_D/.beyin-version")"
  else
    echo "  sürüm: v1 (.beyin-version yok)"
  fi
  if [ -f "$BEYIN_D/.beyin-multi-version" ]; then
    echo "  Respot multi-AI: $(sed -n '1p' "$BEYIN_D/.beyin-multi-version")"
  else
    echo "  Respot multi-AI: yok"
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
| Aday var, `.beyin-version` yok | **MODE B, v1'den yükseltme** (PHASE U1'e git) |
| Aday var, `.beyin-version` = `2.0.0`, `.beyin-multi-version` yok | **MODE B**, Respot katmanını tamamla |
| İki damga da `2.0.0` / `1.0.0` | Zaten Respot Brain. Sadece `beyin-doktor` çalıştır |
| Aday var, `.beyin-version` başka bir değer | Kullanıcıya göster, ne yapılacağını sor |

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
6. **Hangi agentları kullanıyorsun?** Claude Code, Codex, Cursor, Antigravity arasından seçtir.
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

**v2 hard requirement:** `python3` and at least one supported authenticated local AI CLI must be
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
for BEYIN_CLI in claude codex agy cursor-agent; do
  if command -v "$BEYIN_CLI" >/dev/null 2>&1; then
    echo "$BEYIN_CLI CLI ✓ $(command -v "$BEYIN_CLI")"
    BEYIN_CLI_COUNT=$((BEYIN_CLI_COUNT + 1))
  fi
done
if [ "$BEYIN_CLI_COUNT" -eq 0 ]; then
  echo "🔴 DESTEKLENEN AI CLI YOK: claude | codex | agy | cursor-agent"
  BEYIN_MISSING=$((BEYIN_MISSING + 1))
fi
echo "ONKOSUL SONUC: $BEYIN_MISSING eksik"
```

`ONKOSUL SONUC: 0` is the only line that lets you continue. `python3` is what the background
summarizer and the compiler run on, and it is the entire v2 thesis. If it is missing:

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

Verify the v2 pieces landed:

```bash
cd "{{VAULT_PATH}}"
ls .claude/hooks/          # session-start.sh prompt-counter.sh session-end.sh pre-compact.sh lib.sh
ls .claude/scripts/        # flush.py compile.py
ls .claude/skills/         # beyin-doktor gecmis-import
ls -d daily knowledge/concepts knowledge/connections
cat .beyin-version         # 2.0.0
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
python3 scripts/render_integrations.py
python3 scripts/render_integrations.py --check
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

Show the listed files. Only after approval, repeat the exact command with `--apply`. The installer
merges existing user rules/hooks, takes a backup, installs global skills, and avoids double-running
when the vault itself is the active workspace. Leave `.beyin/config.json` at
`{"summary_provider":"auto"}` unless the user explicitly chooses another provider; if they do:

```bash
cd "{{VAULT_PATH}}" && python3 scripts/set_summary_provider.py <provider>
```

## PHASE 4: Git (new in v2)

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
3. Tell the user it is an upgrade layer. The file-based memory and the whole v2 pipeline work
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
python3 -m py_compile .claude/scripts/flush.py .claude/scripts/compile.py && echo "scriptler ✓"
```

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

# MODE B: Upgrade an existing v1 vault directly to Respot Brain

> The user already has a working brain. Their memory files are the whole point of it. This mode is
> **additive only**, with exactly one exception that v2 makes mandatory: the memory folder must be
> named `🔮 850-Companion`, because the hooks and the scripts read that fixed path.

## Run the script. Do not hand-roll the upgrade in fenced blocks.

Every Bash call you make is a **separate process**. A variable you set in one fenced block
(`V="..."`, `R="$(pwd)"`) is gone in the next one. The old runbook did exactly that, and the
result was real: `"$V/daily"` expanded to `/daily`, `"$V/.beyin-version"` to `/.beyin-version`,
and the version stamp was written before the checks that were supposed to justify it.

So the entire upgrade lives in one committed, versioned script:

```
scripts/upgrade.sh
```

Every call carries the vault path as an argument, so there is nothing to lose between calls. The
script runs `set -euo pipefail`, derives the repo path from its own location, canonicalizes both
paths, and refuses an empty path, `/`, `$HOME`, the repo itself, a path that contains the repo or
sits inside it, and any directory without the v1 markers (`CLAUDE.md` plus a `🔮 850-*` folder).

## The upgrade contract (read it out loud to yourself before you type)

**NEVER touch:**
- `🔮 850-Companion/*.md` (whatever the folder was called before): Core, Last-Session, Threads,
  Journal. Not a rewrite, not a reformat, not a "small cleanup". Kurallar.md is seeded **only if
  it does not exist**.
- `🎯 100-Command-Center/Dashboard.md` and every other note the user or the companion wrote.
- `CLAUDE.md`. It carries the user's personalization. You may *append* a short v2 section at the
  end if the user says yes, and only then.
- Secrets in `.claude/settings.local.json` (`env`, API keys), unrelated hooks, permissions, and
  every other key in that file.

**UNTRACKED FROM GIT (file stays on disk, contents untouched):**
- `.claude/settings.local.json`, `.env`, and any leftover `*.yedek` / `*.bak` / `*.orig`, if the
  v1 vault had them committed. Adding a `.gitignore` rule does not untrack an already-tracked
  path, so the upgrade runs `git rm --cached` on them before taking its snapshot. Without this
  the run dies at the final commit gate with every check green and no way forward.
- Tell the user plainly: **the secret is still in the repository history.** If that file held an
  API key, they should revoke and reissue it at the provider. Rewriting history is a separate
  job (`git filter-repo` or BFG) and the upgrade will not attempt it.

**ADD (only if absent):**
- `daily/`, `knowledge/`, `knowledge/concepts/`, `knowledge/connections/` with their `.gitkeep`s
- `knowledge/index.md`, `knowledge/log.md`
- `.claude/scripts/` (flush.py, compile.py, `.state/`)
- `.claude/skills/beyin-doktor/`, `.claude/skills/gecmis-import/`
- `🔮 850-Companion/Kurallar.md`
- `.beyin/` canonical instructions, provider config, bridge, model runner and shared skills
- `AGENTS.md`, `.agents/`, `.codex/`, `.cursor/` provider-native adapters
- `.beyin-multi-version`, written only after every gate passed
- `.beyin-version`, the authoritative stamp written **last of all**
- missing `.gitignore` entries

**REPLACE:**
- `.claude/hooks/*.sh` and `.claude/hooks/lib.sh`. These are code, not memory. The v2 versions are
  strict supersets of v1 behavior. The pre-upgrade snapshot holds any local edits.

**RENAME (mandatory in v2, with the user's explicit yes):**
- A memory folder named after the companion (`🔮 850-Echo`) becomes `🔮 850-Companion`, with
  `git mv`. Contents are never copied and never deleted; a rename is a rename. If the user says
  no, the upgrade does not happen at all and `.beyin-version` is not written.

**MERGE, idempotently:**
- `.claude/settings.json` hook wiring. An event already wired to the same hook file is skipped,
  never duplicated. Running the upgrade twice produces the exact same file.
- `.claude/settings.local.json`: only the exact v1 beyin hook commands are removed. Unrelated
  matchers, unrelated events and every other key survive untouched.

## PHASE U1: Plan (read only, changes nothing)

```bash
bash scripts/upgrade.sh --vault "/kullanicinin/mutlak/vault/yolu" --stage check
```

Use the absolute path you confirmed in PHASE M, in double quotes: it has spaces and emoji in it.
The command prints the plan, the current memory folder name, how many v1 hooks live in
`settings.local.json`, and an `ONAY GEREKLİ` list when confirmations are needed. It touches
nothing. Read it back to the user in Turkish.

## PHASE U2: Get the confirmations, in Turkish, out loud

Ask only what `--stage check` actually asked for.

1. **Hafıza klasörü adı.** If it is not `🔮 850-Companion`:
   > "Hafıza klasörünün adı `🔮 850-Echo`. v2'nin kancaları ve scriptleri sabit
   > `🔮 850-Companion` yolunu okuyor, bu yüzden bu yeniden adlandırma v2 için zorunlu. İçerik hiç
   > değişmiyor, sadece klasörün adı değişiyor; ortağının ismi zaten dosyaların içinde yazıyor.
   > Onaylıyor musun?"

   Yes → pass `--confirm-rename`.
   No → **stop the upgrade here.** Say in Turkish that the vault stays on v1, nothing was changed
   and no version was stamped. Do not run `apply`. Do not write `.beyin-version`. A vault stamped
   `2.0.0` whose memory injection cannot find the folder is worse than an honest v1 vault.

2. **`settings.local.json` içindeki v1 kancaları.** If the check found any:
   > "Eski kurulumda kancalar `settings.local.json` içine yazılmış. v2 bunları `settings.json`
   > içine alıyor. Eskiler silinmezse her olayda kancalar iki kez çalışır ve aynı gün iki kez
   > loglanır. Sadece bu dört kanca girdisi siliniyor; API anahtarın, izinlerin ve kendi yazdığın
   > diğer kancalar aynen kalıyor. Silmeden önce yedeği repo ve vault dışına, sadece senin
   > okuyabileceğin izinle alıyorum. Onaylıyor musun?"

   Yes → pass `--confirm-local-hooks`.
   No → **stop the upgrade here**, same rule. Never stamp a version on a vault that fires every
   hook twice.

## PHASE U3: Apply

```bash
bash scripts/upgrade.sh --vault "/kullanicinin/mutlak/vault/yolu" --stage apply --confirm-rename --confirm-local-hooks
```

Pass only the confirmation flags the check asked for. Read the numbered output back to the user.

| Çıkış kodu | Anlamı | Ne yapacaksın |
| --- | --- | --- |
| `0` | Respot çekirdeği ve adapterları hazır, iki sürüm damgası da HENÜZ yazılmadı | PHASE U4'e geç |
| `3` | vault zaten çekirdek `2.0.0` + Respot multi-AI `1.0.0` | yükseltme yok, sadece `beyin doktor` çalıştır |
| `10` | yeniden adlandırma onayı eksik | PHASE U2'ye dön |
| `11` | yerel kanca temizliği onayı eksik | PHASE U2'ye dön |
| `1` | sert hata, ekranda `HATA:` satırı var | DUR. Kullanıcıya oku, düzelt, tekrar çalıştır |

On exit `1` nothing is stamped and the pre-upgrade snapshot is already in the vault's git history,
so `git reset --hard <anlık görüntü>` inside the vault puts everything back. Say that out loud
instead of improvising a repair.

## PHASE U4: Resolve the placeholders in the newly added files

`apply` prints the files that still contain `{{...}}`. Read `CLAUDE.md` and the existing memory
files to recover the user's name and the companion's name, and fill them in. Do not ask the user
to repeat what the vault already knows; confirm your reading in one line instead:
"Ortağının adı X, senin adın Y, doğru mu?"

```bash
grep -rl "{{" "/kullanicinin/mutlak/vault/yolu/knowledge" \
              "/kullanicinin/mutlak/vault/yolu/.claude/skills" \
              "/kullanicinin/mutlak/vault/yolu/.beyin" \
              "/kullanicinin/mutlak/vault/yolu/.agents" \
              "/kullanicinin/mutlak/vault/yolu/.cursor" \
              "/kullanicinin/mutlak/vault/yolu/AGENTS.md" \
              "/kullanicinin/mutlak/vault/yolu/CLAUDE.md" \
              "/kullanicinin/mutlak/vault/yolu/🔮 850-Companion" 2>/dev/null \
  || echo "✓ çözülmemiş placeholder yok"
```

## PHASE U5: Doctor

Ask the agent currently performing the setup to run the `beyin-doktor` skill against the vault.
The same canonical skill is available to Claude, Codex, Cursor and Antigravity after the multi-AI
layer is enabled. If skill discovery is not yet active, run the manual checks from PHASE 7.

Close every 🔴 row before you go on. The version has not been stamped yet, so the doctor is
looking at an honest half-upgraded vault. That is the point.

## PHASE U6: Finalize (the only step that writes both Respot version stamps)

```bash
bash scripts/upgrade.sh --vault "/kullanicinin/mutlak/vault/yolu" --stage finalize
```

`finalize` re-runs every gate from scratch, in this order:

1. memory folder is exactly `🔮 850-Companion`
2. all five hooks present, executable, `bash -n` clean, recursion guard line present
3. both scripts present and byte-compilable
4. both skills present
5. every added folder and seed file present
6. no `{{...}}` left in any file the upgrade added
7. across `settings.json` **and** `settings.local.json` together, exactly one effective handler per
   event: SessionStart, UserPromptSubmit, SessionEnd, PreCompact
8. no secret-bearing backup left anywhere inside the vault
9. `.gitignore` actually protects `.claude/settings.local.json`
10. canonical `.beyin/` sources, provider config and four agent adapter families are present
11. generated rules/hooks have no drift from `.beyin/`
12. neither `.beyin-version` nor `.beyin-multi-version` was written early

Only if all twelve pass does it commit with an **explicit path allow-list** (never `git add -A`),
abort if any staged path looks like local settings or a backup, verify that `HEAD` really moved,
and only then write `.beyin-multi-version = 1.0.0` followed by the authoritative final
`.beyin-version = 2.0.0` write. If any gate fails it prints the failing rows, writes no stamp, and
the vault stays honestly unfinished. A vault that already has only the old v2 core stamp is not
treated as complete; the same upgrade finishes its Respot layer.

Then offer this in one Turkish line, do not push it: **"Eski ChatGPT, Claude veya Gemini geçmişini
de bu beyne aktarmak ister misin? `geçmiş import` yeter."** The `gecmis-import` skill does
everything locally; nothing is uploaded anywhere. Large exports take several evenings to compile,
and that is fine.

## PHASE U7: Optional global access

The upgrade itself already installed the full provider-neutral Respot workspace layer. Do **not**
run a second `enable_multiai.py` migration. Follow PHASE 3B only if the user wants the same vault
available automatically in unrelated code repositories. Keep summary provider `auto` unless the
user explicitly requests another first choice.

## What the script guarantees, so you do not have to promise it yourself

- **One process.** No variable survives between your Bash calls, so none is used across them.
- **Verified snapshot.** `git init` when needed, always with an explicit `-c user.name` and
  `-c user.email`, so an unset git identity cannot turn a failed commit into "değişiklik yok".
  It compares `HEAD` before and after and refuses to continue if the commit did not actually
  happen. With no git at all it takes a copy outside the vault and verifies the item count.
- **Secrets stay out of git.** The `.gitignore` entries are installed **before** the first
  snapshot, the `settings.local.json` backup is written outside both the repo and the vault with
  mode `0600`, and every staging step aborts if a path matching local settings, `.yedek`, `.bak`,
  `.env`, `.pem` or `.key` reaches the index.
- **Never destroy.** Every copy is checked, the rename compares the item count before and after,
  seed files are skipped when they already exist, and the `settings.local.json` rewrite drops only
  the four exact v1 beyin commands.
- **Idempotent.** Running `apply` twice prints `eklenen kanca girdisi: 0`, skips every seed and
  reports the memory folder as already correct. A fully stamped Respot vault exits `3`; a vault
  with only the old v2 core stamp is completed instead of being falsely reported as finished.

# THE DEMO (both modes end here)

Report in Turkish:

- ✅ **Ne kuruldu:** vault yolu ve kullanıcı seçtiği adı, hafıza motoru, `daily/`, `knowledge/`,
  canonical rules/skills, kurulan workspace adaptörleri ve varsa global provider bağlantıları.
- 🔁 **Agent değiştirme:** bir agentın kapanış özeti ortak vault'a yazıldıktan sonra diğer agent
  aynı bağlamı alır; sağlayıcının ham chat UI geçmişi taşınmaz.
- 🤖 **Özetleyici:** varsayılan `auto`; mevcut agent önce denenir, geçici limitte kurulu ve giriş
  yapılmış başka CLI'a fallback edilir. Kalıcı seçim yalnız kullanıcı isterse yapılır.
- ▶️ **İlk çalıştırma:** Obsidian'da `{{VAULT_PATH}}` klasörünü bir kez vault olarak aç. Sonra
  kullanıcının ana agentında kısa ama anlamlı bir test konuşması başlat.

## Prove one real lifecycle

The exact close action depends on the host: Claude CLI may use `/exit`; Codex, Cursor and
Antigravity use their own end/close controls. Do not prescribe `/exit` to every product. Ask the
user to end the test session normally, then poll for the daily log:

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

- **Daily log:** starts at a supported session-end/pre-compact event and normally takes seconds.
- **Knowledge compile:** starts after 18:00 on the next eligible session close. If that window is
  missed, the next session start catches up completed earlier days without ingesting today's
  partial log. It can take minutes. There is no scheduler opening an AI app by itself.
- **Quota:** usage belongs to whichever CLI actually answered. Retryable limit/timeout/5xx errors
  fall through to another installed CLI. Authentication/configuration failures stop visibly.

Do not end with only "kuruldu". Report the tested provider, whether fallback alternatives are
actually installed/authenticated, the global backup path, and any one-time action still needed
(for example Codex `/hooks` trust or restarting an IDE to reload user hooks).

Done. The user now has one portable memory layer instead of four disconnected agent memories.
