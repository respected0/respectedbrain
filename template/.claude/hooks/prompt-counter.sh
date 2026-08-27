#!/bin/bash
[ -n "${BEYIN_INVOKED_BY:-}" ] && exit 0
# Count prompts and nudge at every multiple of fifteen.

BEYIN_HOOK_DIR=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd)
. "$BEYIN_HOOK_DIR/lib.sh" 2>/dev/null || exit 0

BEYIN_SESSION_KEY=$(beyin_session_key 2>/dev/null || :)
[ -n "$BEYIN_SESSION_KEY" ] || exit 0

BEYIN_PROMPT_COUNT_FILE="$BEYIN_STATE_DIR/prompt_count.$BEYIN_SESSION_KEY"
BEYIN_LOCK_FILE="$BEYIN_PROMPT_COUNT_FILE.lock"
BEYIN_LOCK_ATTEMPT=0
BEYIN_LOCK_ACQUIRED=0
set -o noclobber
while [ "$BEYIN_LOCK_ACQUIRED" -eq 0 ]; do
  if { : > "$BEYIN_LOCK_FILE"; } 2>/dev/null; then
    BEYIN_LOCK_ACQUIRED=1
    break
  fi
  BEYIN_LOCK_ATTEMPT=$((BEYIN_LOCK_ATTEMPT + 1))
  [ "$BEYIN_LOCK_ATTEMPT" -lt 100000 ] || {
    set +o noclobber
    exit 0
  }
done
set +o noclobber
trap 'rm -f "$BEYIN_LOCK_FILE" 2>/dev/null || :' EXIT
trap 'exit 0' HUP INT TERM

BEYIN_COUNT=0
if [ -f "$BEYIN_PROMPT_COUNT_FILE" ]; then
  BEYIN_COUNT=$(sed -n '1p' "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :)
fi
case "$BEYIN_COUNT" in
  ''|*[!0-9]*) BEYIN_COUNT=0 ;;
esac

BEYIN_COUNT=$((BEYIN_COUNT + 1))
BEYIN_COUNT_TMP="$BEYIN_PROMPT_COUNT_FILE.tmp.$$"
if printf '%s\n' "$BEYIN_COUNT" > "$BEYIN_COUNT_TMP" 2>/dev/null; then
  mv -f "$BEYIN_COUNT_TMP" "$BEYIN_PROMPT_COUNT_FILE" 2>/dev/null || :
fi
rm -f "$BEYIN_COUNT_TMP" 2>/dev/null || :
rm -f "$BEYIN_LOCK_FILE" 2>/dev/null || :
trap - EXIT HUP INT TERM

if [ $((BEYIN_COUNT % 15)) -eq 0 ]; then
  beyin_emit UserPromptSubmit "[Hafıza] $BEYIN_COUNT. mesaj. Oturum sonunda 🔮 850-Companion/Last-Session.md ve Threads.md güncellemeyi unutma."
fi
exit 0
