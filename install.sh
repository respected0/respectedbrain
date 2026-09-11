#!/usr/bin/env bash
# Respected Brain v0.0.1 — Linux & macOS One-Liner Kurulum Başlatıcı

set -euo pipefail

echo ">> Respected Brain v0.0.1 — Kurulum Başlatıcı"

# 1. Python Tespiti ve Otomatik Yükleme Teklifi
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "UYARI: Sisteminizde Python 3 bulunamadı." >&2
    AUTO_INSTALL="no"
    if [ -t 0 ]; then
        read -r -p "Python 3 paket yöneticisi ile otomatik kurulsun mu? [E/h]: " USER_RESP || true
        case "${USER_RESP:-E}" in
            [eE]|[eE][vV][eE][tT]|[yY]|[yY][eE][sS]|"") AUTO_INSTALL="yes" ;;
        esac
    fi

    if [ "${AUTO_INSTALL}" = "yes" ]; then
        if command -v apt-get >/dev/null 2>&1; then
            echo "Python 3 kuruluyor (apt)..."
            sudo apt-get update && sudo apt-get install -y python3
        elif command -v brew >/dev/null 2>&1; then
            echo "Python 3 kuruluyor (brew)..."
            brew install python3
        elif command -v dnf >/dev/null 2>&1; then
            echo "Python 3 kuruluyor (dnf)..."
            sudo dnf install -y python3
        elif command -v pacman >/dev/null 2>&1; then
            echo "Python 3 kuruluyor (pacman)..."
            sudo pacman -Sy --noconfirm python
        fi
        if command -v python3 >/dev/null 2>&1; then
            PYTHON_BIN="python3"
        fi
    fi

    if [ -z "${PYTHON_BIN}" ]; then
        echo "HATA: Python 3 bulunamadı. Lütfen sisteminize python3 yükleyin." >&2
        exit 1
    fi
fi

# 2. install.py tespiti veya indirme
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || pwd)"
INSTALL_PY="${SCRIPT_DIR}/install.py"

if [ ! -f "${INSTALL_PY}" ]; then
    TMP_DIR="$(mktemp -d -t respected-brain-install-XXXXXX)"
    echo "• Repo indiriliyor..."
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 https://github.com/respected0/secondbrain.git "${TMP_DIR}" >/dev/null 2>&1
        INSTALL_PY="${TMP_DIR}/install.py"
    else
        echo "• Git tespit edilemedi, GitHub arşivi indiriliyor..."
        ZIP_FILE="${TMP_DIR}/repo.zip"
        if command -v curl >/dev/null 2>&1; then
            curl -sSL "https://github.com/respected0/secondbrain/archive/refs/heads/main.zip" -o "${ZIP_FILE}"
        elif command -v wget >/dev/null 2>&1; then
            wget -q "https://github.com/respected0/secondbrain/archive/refs/heads/main.zip" -O "${ZIP_FILE}"
        fi
        if command -v unzip >/dev/null 2>&1; then
            unzip -q "${ZIP_FILE}" -d "${TMP_DIR}"
            rm -f "${ZIP_FILE}"
            if [ -d "${TMP_DIR}/secondbrain-main" ]; then
                INSTALL_PY="${TMP_DIR}/secondbrain-main/install.py"
            else
                INSTALL_PY="${TMP_DIR}/install.py"
            fi
        else
            echo "HATA: git veya unzip bulunamadı. Lütfen sisteminize git veya unzip kurun." >&2
            exit 1
        fi
    fi
    trap 'rm -rf "${TMP_DIR}"' EXIT
fi

# 3. install.py'ı argümanlarla çalıştır
exec "${PYTHON_BIN}" "${INSTALL_PY}" "$@"
