#!/bin/bash
set -eu

MODE=${1:-check}
REMOTE=${BEYIN_UPSTREAM_REMOTE:-upstream}
BRANCH=${BEYIN_UPSTREAM_BRANCH:-main}

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Hata: bir Git deposunda değilsin." >&2
  exit 1
}
git remote get-url "$REMOTE" >/dev/null 2>&1 || {
  echo "Hata: '$REMOTE' remote'u yok. Önce upstream'i ekle." >&2
  exit 1
}

git fetch "$REMOTE" "$BRANCH"
echo "Yerel HEAD:    $(git rev-parse --short HEAD)"
echo "Upstream HEAD: $(git rev-parse --short "$REMOTE/$BRANCH")"
git log --oneline --decorate HEAD.."$REMOTE/$BRANCH" || :

case "$MODE" in
  check)
    echo "Yalnızca kontrol edildi; çalışma ağacı değiştirilmedi."
    ;;
  merge)
    [ -z "$(git status --porcelain)" ] || {
      echo "Hata: çalışma ağacı kirli. Önce commit veya stash yap." >&2
      exit 1
    }
    BACKUP_BRANCH="backup/before-upstream-$(date '+%Y%m%d-%H%M%S')"
    git branch "$BACKUP_BRANCH" HEAD
    echo "Geri dönüş dalı: $BACKUP_BRANCH"
    git merge --no-commit --no-ff "$REMOTE/$BRANCH"
    echo "Birleştirme çalışma ağacında. Test et; sonra commit at veya birleştirmeyi iptal et."
    ;;
  *)
    echo "Kullanım: $0 [check|merge]" >&2
    exit 2
    ;;
esac
