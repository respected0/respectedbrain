#!/usr/bin/env bash
# Respected Brain v0.0.1 — Linux & macOS One-Liner Güncelleme Başlatıcı

set -euo pipefail

echo ">> Respected Brain v0.0.1 — Güncelleme Başlatıcı"

# 1. Python Tespiti
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "HATA: Python 3 bulunamadı. Lütfen sisteminize python3 yükleyin." >&2
    exit 1
fi

# 2. update.py tespiti veya indirme
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || pwd)"
UPDATE_PY="${SCRIPT_DIR}/update.py"

if [ ! -f "${UPDATE_PY}" ]; then
    TMP_DIR="$(mktemp -d -t respected-brain-update-XXXXXX)"
    echo "• Güncelleme paketi indiriliyor..."
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 https://github.com/respected0/secondbrain.git "${TMP_DIR}" >/dev/null 2>&1
        UPDATE_PY="${TMP_DIR}/update.py"
    else
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
                UPDATE_PY="${TMP_DIR}/secondbrain-main/update.py"
            else
                UPDATE_PY="${TMP_DIR}/update.py"
            fi
        else
            echo "HATA: git veya unzip bulunamadı." >&2
            exit 1
        fi
    fi
    trap 'rm -rf "${TMP_DIR}"' EXIT
fi

# 3. update.py'ı argümanlarla çalıştır
exec "${PYTHON_BIN}" "${UPDATE_PY}" "$@"
