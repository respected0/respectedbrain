#!/bin/bash
# Integration tests for scripts/upstream_sync.sh
set -euo pipefail

TEST_ROOT=$(CDPATH= cd "$(dirname "$0")/.." 2>/dev/null && pwd)
SCRIPT="$TEST_ROOT/scripts/upstream_sync.sh"

TEST_COUNT=0
FAIL_COUNT=0

pass() {
  TEST_COUNT=$((TEST_COUNT + 1))
  printf 'ok %s - %s\n' "$TEST_COUNT" "$1"
}

fail() {
  TEST_COUNT=$((TEST_COUNT + 1))
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf 'not ok %s - %s\n' "$TEST_COUNT" "$1"
}

diag() {
  printf '# %s\n' "$*" >&2
}

TMP_BASE=$(mktemp -d "${TMPDIR:-/tmp}/upstream-sync-test.XXXXXX")
trap 'rm -rf "$TMP_BASE"' EXIT HUP INT TERM

# Ensure git author and isolated environment
export GIT_AUTHOR_NAME="Test Runner"
export GIT_AUTHOR_EMAIL="test@example.com"
export GIT_COMMITTER_NAME="Test Runner"
export GIT_COMMITTER_EMAIL="test@example.com"
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null

# -----------------------------------------------------------------------------
# Test 1: Non-git directory fails with code 1
# -----------------------------------------------------------------------------
NON_GIT_DIR="$TMP_BASE/non_git"
mkdir -p "$NON_GIT_DIR"

set +e
OUT=$(cd "$NON_GIT_DIR" && bash "$SCRIPT" 2>&1)
RC=$?
set -e

if [ "$RC" -eq 1 ] && echo "$OUT" | grep -q "bir Git deposunda değilsin"; then
  pass "git dışı dizinde exit 1 ve açıklayıcı hata mesajı verildi"
else
  fail "git dışı dizin kontrolü başarısız (rc=$RC, out=$OUT)"
fi

# -----------------------------------------------------------------------------
# Test 2: Git repo without upstream remote fails with code 1
# -----------------------------------------------------------------------------
REPO_NO_REMOTE="$TMP_BASE/repo_no_remote"
mkdir -p "$REPO_NO_REMOTE"
git -C "$REPO_NO_REMOTE" init -q -b main

set +e
OUT=$(cd "$REPO_NO_REMOTE" && bash "$SCRIPT" 2>&1)
RC=$?
set -e

if [ "$RC" -eq 1 ] && echo "$OUT" | grep -q "'upstream' remote'u yok"; then
  pass "upstream remote'u olmayan depoda exit 1 ve hata mesajı verildi"
else
  fail "upstream remote yokluğu kontrolü başarısız (rc=$RC, out=$OUT)"
fi

# -----------------------------------------------------------------------------
# Test 3: Custom BEYIN_UPSTREAM_REMOTE is validated
# -----------------------------------------------------------------------------
set +e
OUT=$(cd "$REPO_NO_REMOTE" && BEYIN_UPSTREAM_REMOTE="custom_target" bash "$SCRIPT" 2>&1)
RC=$?
set -e

if [ "$RC" -eq 1 ] && echo "$OUT" | grep -q "'custom_target' remote'u yok"; then
  pass "özel BEYIN_UPSTREAM_REMOTE adı hata mesajında doğrulandı"
else
  fail "özel remote kontrolü başarısız (rc=$RC, out=$OUT)"
fi

# -----------------------------------------------------------------------------
# Test 4: Invalid mode returns code 2
# -----------------------------------------------------------------------------
# Setup remote repo for valid remote tests
UPSTREAM_REPO="$TMP_BASE/upstream.git"
git init --bare -q -b main "$UPSTREAM_REPO"

LOCAL_REPO="$TMP_BASE/local_repo"
git clone -q "$UPSTREAM_REPO" "$LOCAL_REPO"
git -C "$LOCAL_REPO" checkout -q -b main 2>/dev/null || :
echo "initial" > "$LOCAL_REPO/file.txt"
git -C "$LOCAL_REPO" add file.txt
git -C "$LOCAL_REPO" commit -q -m "initial commit"
git -C "$LOCAL_REPO" push -q -u origin main
git -C "$LOCAL_REPO" remote add upstream "$UPSTREAM_REPO"

set +e
OUT=$(cd "$LOCAL_REPO" && bash "$SCRIPT" invalid_mode 2>&1)
RC=$?
set -e

if [ "$RC" -eq 2 ] && echo "$OUT" | grep -q "Kullanım: .* \[check|merge\]"; then
  pass "geçersiz mod verildiğinde exit 2 ve kullanım bilgisi basıldı"
else
  fail "geçersiz mod kontrolü başarısız (rc=$RC, out=$OUT)"
fi

# -----------------------------------------------------------------------------
# Test 5: Mode 'check' fetches upstream and leaves worktree untouched
# -----------------------------------------------------------------------------
# Push an update to upstream from a second clone
OTHER_CLONE="$TMP_BASE/other_clone"
git clone -q "$UPSTREAM_REPO" "$OTHER_CLONE"
echo "upstream update" >> "$OTHER_CLONE/file.txt"
git -C "$OTHER_CLONE" commit -q -am "upstream commit 2"
git -C "$OTHER_CLONE" push -q origin main

HEAD_BEFORE=$(git -C "$LOCAL_REPO" rev-parse HEAD)

set +e
OUT=$(cd "$LOCAL_REPO" && bash "$SCRIPT" check 2>&1)
RC=$?
set -e

HEAD_AFTER=$(git -C "$LOCAL_REPO" rev-parse HEAD)

if [ "$RC" -eq 0 ] && \
   [ "$HEAD_BEFORE" = "$HEAD_AFTER" ] && \
   echo "$OUT" | grep -q "Yalnızca kontrol edildi; çalışma ağacı değiştirilmedi" && \
   echo "$OUT" | grep -q "Yerel HEAD:" && \
   echo "$OUT" | grep -q "Upstream HEAD:"; then
  pass "check modu upstream'i çekti ve yerel HEAD ile çalışma ağacını değiştirmedi"
else
  fail "check modu testi başarısız (rc=$RC, out=$OUT)"
fi

# Also test default mode is 'check'
set +e
OUT_DEFAULT=$(cd "$LOCAL_REPO" && bash "$SCRIPT" 2>&1)
RC_DEFAULT=$?
set -e

if [ "$RC_DEFAULT" -eq 0 ] && echo "$OUT_DEFAULT" | grep -q "Yalnızca kontrol edildi; çalışma ağacı değiştirilmedi"; then
  pass "varsayılan argümansız çağrı check modunu çalıştırdı"
else
  fail "varsayılan mod testi başarısız (rc=$RC_DEFAULT, out=$OUT_DEFAULT)"
fi

# -----------------------------------------------------------------------------
# Test 6: Mode 'merge' with dirty working tree fails with code 1
# -----------------------------------------------------------------------------
echo "uncommitted change" >> "$LOCAL_REPO/file.txt"

set +e
OUT=$(cd "$LOCAL_REPO" && bash "$SCRIPT" merge 2>&1)
RC=$?
set -e

# Verify no backup branch was created
BACKUP_BRANCHES=$(git -C "$LOCAL_REPO" branch --list 'backup/before-upstream-*')

if [ "$RC" -eq 1 ] && \
   echo "$OUT" | grep -q "çalışma ağacı kirli" && \
   [ -z "$BACKUP_BRANCHES" ]; then
  pass "kirli çalışma ağacında merge reddedildi ve yedek dal oluşturulmadı"
else
  fail "kirli çalışma ağacı kontrolü başarısız (rc=$RC, branches=$BACKUP_BRANCHES, out=$OUT)"
fi

# -----------------------------------------------------------------------------
# Test 7: Mode 'merge' with clean working tree creates backup and merges --no-commit
# -----------------------------------------------------------------------------
# Discard dirty change
git -C "$LOCAL_REPO" checkout -q -- file.txt

set +e
OUT=$(cd "$LOCAL_REPO" && bash "$SCRIPT" merge 2>&1)
RC=$?
set -e

BACKUP_BRANCHES=$(git -C "$LOCAL_REPO" branch --list 'backup/before-upstream-*')
MERGE_HEAD_EXISTS=0
if [ -f "$LOCAL_REPO/.git/MERGE_HEAD" ]; then
  MERGE_HEAD_EXISTS=1
fi

if [ "$RC" -eq 0 ] && \
   [ -n "$BACKUP_BRANCHES" ] && \
   [ "$MERGE_HEAD_EXISTS" -eq 1 ] && \
   echo "$OUT" | grep -q "Geri dönüş dalı:" && \
   echo "$OUT" | grep -q "Birleştirme çalışma ağacında"; then
  pass "temiz ağaçta yedek dal oluşturuldu ve --no-commit ile birleştirme hazırlandı"
else
  fail "temiz merge kontrolü başarısız (rc=$RC, merge_head=$MERGE_HEAD_EXISTS, out=$OUT)"
fi

# Abort the merge to clean up local repo
git -C "$LOCAL_REPO" merge --abort

# Wait 1 second so backup branch timestamp does not collide with Test 7
sleep 1

# -----------------------------------------------------------------------------
# Test 8: Custom BEYIN_UPSTREAM_BRANCH works as intended
# -----------------------------------------------------------------------------
# Create custom branch on other clone and push to upstream
git -C "$OTHER_CLONE" checkout -q -b custom-release
echo "custom release content" > "$OTHER_CLONE/custom.txt"
git -C "$OTHER_CLONE" add custom.txt
git -C "$OTHER_CLONE" commit -q -m "custom branch commit"
git -C "$OTHER_CLONE" push -q -u origin custom-release

set +e
OUT=$(cd "$LOCAL_REPO" && BEYIN_UPSTREAM_BRANCH="custom-release" bash "$SCRIPT" merge 2>&1)
RC=$?
set -e

if [ "$RC" -eq 0 ] && [ -f "$LOCAL_REPO/.git/MERGE_HEAD" ]; then
  pass "özel BEYIN_UPSTREAM_BRANCH başarıyla çekildi ve birleştirildi"
else
  fail "özel dal merge kontrolü başarısız (rc=$RC, out=$OUT)"
fi

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
