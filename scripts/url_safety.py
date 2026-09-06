#!/usr/bin/env python3
"""URL Güvenlik ve SSRF Kalkanı - Respected Brain.

Ajanların otonom web araştırması, sayfa çekme veya scraping yaparken
yerel ağa (LAN), localhost'a, intranet adreslerine veya özel portlara
(SSRF - Server Side Request Forgery) sızmasını engeller.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import socket
import sys
from urllib.parse import urlparse

# Standart izin verilen portlar
ALLOWED_PORTS = {80, 443}

# Yasaklı yerel/özel host isimleri
DISALLOWED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "broadcasthost",
    "local",
    "internal",
}


def is_private_or_reserved_ip(ip_str: str) -> bool:
    """Verilen IP adresinin özel, yerel veya rezerve olup olmadığını doğrular."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_safe_url(url: str) -> tuple[bool, str]:
    """Bir URL'in dış ağ için güvenli olup olmadığını doğrular.

    Döndürür:
        (is_safe: bool, reason: str)
    """
    if not isinstance(url, str) or not url.strip():
        return False, "URL boş veya geçersiz"

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL ayrıştırma hatası: {e}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Desteklenmeyen protokol: {parsed.scheme} (Yalnızca http/https)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Geçerli bir hostname bulunamadı"

    hostname_clean = hostname.lower().strip(".")

    # Yasaklı hostname kontrolü
    if hostname_clean in DISALLOWED_HOSTNAMES or hostname_clean.endswith(".local") or hostname_clean.endswith(".internal"):
        return False, f"Yerel ve dahili ağ hostlarına erişim engellendi: {hostname}"

    # Port kontrolü
    port = parsed.port
    if port is not None and port not in ALLOWED_PORTS:
        return False, f"Güvensiz port: {port} (Yalnızca 80 ve 443 portlarına izin verilir)"

    # Doğrudan IP adresi kontrolü
    if is_private_or_reserved_ip(hostname_clean):
        return False, f"Özel/yerel IP adresine erişim engellendi: {hostname_clean}"

    # DNS çözümleme ve çözümlenen IP kontrolü
    try:
        # getaddrinfo ile tüm olası IP'leri çöz
        addr_info = socket.getaddrinfo(hostname_clean, port or (443 if parsed.scheme == "https" else 80))
        for item in addr_info:
            sockaddr = item[4]
            resolved_ip = sockaddr[0]
            if is_private_or_reserved_ip(resolved_ip):
                return False, f"Host çözümlendiğinde özel/yerel IP adresine ulaşıyor ({resolved_ip})"
    except socket.gaierror:
        # DNS çözülemediyse bile host adı genel olarak kabul edilebilir (ağ kapalı olabilir veya test ediliyor olabilir)
        pass
    except Exception as e:
        return False, f"DNS çözümleme güvenlik hatası: {e}"

    return True, "URL güvenli"


def normalize_canonical_text(text: str) -> str:
    """Temizlenmiş kanonik metin gövdesi oluşturur.

    1. HTML ve script etiketlerini ayıklar.
    2. BOM karakterini ve CRLF'yi LF'ye çevirir.
    3. Madde imlerini (* ve +) standart '-' yapar.
    4. Tüm whitespace dizilerini (yeni satırlar dahil) tek bir boşluğa indirir ve kırpar.
    """
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = clean.lstrip("\ufeff")
    clean = clean.replace("\r\n", "\n").replace("\r", "\n")
    clean = re.sub(r"^\s*[\*\+]\s+", "- ", clean, flags=re.MULTILINE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def canonical_content_hash(text: str) -> str:
    """Kanonik metnin ilk 16 karakterlik SHA-256 özetini döndürür.

    Web ve dosya içeriklerinde mükerrer kaydı önlemek için kullanılır.
    """
    canonical = normalize_canonical_text(text)
    if not canonical:
        return ""
    import hashlib
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description="URL Güvenlik ve SSRF Doğrulayıcı")
    parser.add_argument("url", help="Kontrol edilecek URL")
    args = parser.parse_args()

    safe, reason = validate_safe_url(args.url)
    if safe:
        print(f"GÜVENLİ: {args.url}")
        return 0
    else:
        print(f"GÜVENSİZ: {args.url} -> {reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
