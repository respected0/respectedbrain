#!/usr/bin/env bash
# Claude Code Stop Event Hook (Bash Versiyonu)
# Oturumda dosya mutasyonu varsa stderr üzerinden Claude'u uyandırarak
# Last-Session.md ve günün logunu güncellemesini sağlar.

set -euo pipefail

INPUT=$(cat)
[ -z "$INPUT" ] && exit 0

# 1. Sonsuz döngü kontrolü
IS_HOOK_TURN=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('1' if d.get('stop_hook_active') else '0')
except:
    print('0')
" 2>/dev/null || echo "0")

[ "$IS_HOOK_TURN" = "1" ] && exit 0

# 2. Oturum başına 1 kez çalışma kilidi (Sentinel)
SESSION_ID=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', 'default_session'))
except:
    print('default_session')
" 2>/dev/null || echo "default_session")

SENTINEL_DIR="$HOME/.respectedos/hooks/sentinels"
mkdir -p "$SENTINEL_DIR"
SESSION_LOCK="$SENTINEL_DIR/$SESSION_ID"

# Eğer kilit varsa sessizce çık
if [ -d "$SESSION_LOCK" ]; then
    exit 0
fi

# 3. Transkript inceleme (mutasyon var mı?)
TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    print('')
" 2>/dev/null || echo "")

HAS_MUTATION=0
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    if grep -E -q "(write_to_file|replace_file_content|git commit|npm install|pip install)" "$TRANSCRIPT_PATH" 2>/dev/null; then
        HAS_MUTATION=1
    fi
else
    HAS_MUTATION=1
fi

[ "$HAS_MUTATION" = "0" ] && exit 0

# Kilidi atomik oluştur
mkdir "$SESSION_LOCK" 2>/dev/null || exit 0

# Claude'u rewake et (stderr + exit 2)
cat << 'EOF' >&2
[RESPECTED-OS HAFIZA SİSTEMİ BİLDİRİMİ]
Bu oturumda anlamlı kod/dosya değişiklikleri yapıldı.
Oturumu kapatmadan önce lütfen:
1. '🔮 850-Companion/Last-Session.md' dosyasını güncelle.
2. Açık veya tamamlanan işleri 'Threads.md' veya günün 'daily/YYYY-MM-DD.md' loguna kısaca işle.
Hafıza devrini tamamladıktan sonra oturumu sonlandır.
EOF

exit 2
