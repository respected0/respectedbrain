#!/usr/bin/env bash
# ==============================================================================
# Respected Brain v0.0.1 — macOS Tek Tık Kurulum, Bakım & Yönetim Başlatıcı
# Finder'da çift tıklandığında otomatik olarak Terminal'de açılır.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

printf "\033]0;Respected Brain — macOS Kurulum & Yönetim\007"

# 1. Python 3 Kontrolü
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

if [ -z "${PYTHON_BIN}" ]; then
    echo -e "\033[93m[!] Sisteminizde Python 3 bulunamadı.\033[0m"
    if command -v brew >/dev/null 2>&1; then
        read -r -p "Homebrew ile Python 3 otomatik kurulsun mu? [E/h]: " USER_RESP
        case "${USER_RESP:-E}" in
            [eE]|[eE][vV][eE][tT]|[yY]|[yY][eE][sS]|"")
                echo "Python 3 yükleniyor (brew install python)..."
                brew install python
                PYTHON_BIN="python3"
                ;;
            *)
                echo -e "\033[91mPython 3 olmadan kuruluma devam edilemez. Lütfen python.org adresinden yükleyin.\033[0m"
                read -n 1 -s -r -p "Çıkmak için bir tuşa basın..."
                exit 1
                ;;
        esac
    else
        echo -e "\033[91mLütfen python.org adresinden veya Homebrew ile Python 3 yükleyin.\033[0m"
        read -n 1 -s -r -p "Çıkmak için bir tuşa basın..."
        exit 1
    fi
fi

# 2. Evrensel setup.py motorunu çalıştır
"${PYTHON_BIN}" "${SCRIPT_DIR}/setup.py" "$@"

echo ""
read -n 1 -s -r -p "Çıkmak için bir tuşa basın..."
echo ""
