#!/bin/bash
[ -n "${BEYIN_INVOKED_BY:-}" ] && exit 0
# POSIX compatibility launcher; lifecycle policy lives in Python.

if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  BEYIN_PROJECT_DIR=$CLAUDE_PROJECT_DIR
else
  BEYIN_HOOK_DIR=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
  BEYIN_PROJECT_DIR=$(CDPATH= cd "$BEYIN_HOOK_DIR/../.." 2>/dev/null && pwd) || exit 0
fi

exec python3 "$BEYIN_PROJECT_DIR/.beyin/hooks/bridge.py" --provider claude --event end
