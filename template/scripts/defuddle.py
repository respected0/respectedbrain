#!/usr/bin/env python3
"""Defuddle - Web Sayfası Gürültü Sıyırıcı ve Temiz Markdown Çıkarıcı.

HTML içeriklerindeki reklamları, gezinme menülerini, çerez bantlarını,
script ve stilleri temizleyerek LLM modelleri için saf, okunabilir ve
token-verimli Markdown metni üretir.
"""

from __future__ import annotations

import argparse
from html import unescape
from html.parser import HTMLParser
import re
import sys
from typing import Any
import urllib.request

try:
    from url_safety import validate_safe_url
except ImportError:
    try:
        from scripts.url_safety import validate_safe_url
    except ImportError:
        validate_safe_url = lambda u: (True, "ok")


class SimpleHtmlToMarkdown(HTMLParser):
    """HTML içeriğini temiz Markdown'a dönüştüren hafif ayrıştırıcı."""

    DISCARD_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "header",
        "footer",
        "nav",
        "form",
        "iframe",
        "aside",
    }

    def __init__(self) -> None:
        super().__init__()
        self.pieces: list[str] = []
        self.discard_depth = 0
        self.in_pre = False
        self.in_code = False
        self.current_href: str | None = None
        self.link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        if tag_lower in self.DISCARD_TAGS:
            self.discard_depth += 1
            return

        if self.discard_depth > 0:
            return

        attr_dict = dict(attrs)

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_lower[1])
            self.pieces.append(f"\n\n{'#' * level} ")
        elif tag_lower == "p":
            self.pieces.append("\n\n")
        elif tag_lower == "br":
            self.pieces.append("\n")
        elif tag_lower == "li":
            self.pieces.append("\n- ")
        elif tag_lower == "pre":
            self.in_pre = True
            self.pieces.append("\n\n```\n")
        elif tag_lower == "code" and not self.in_pre:
            self.in_code = True
            self.pieces.append("`")
        elif tag_lower == "blockquote":
            self.pieces.append("\n\n> ")
        elif tag_lower == "a":
            href = attr_dict.get("href")
            if href and not href.startswith("javascript:"):
                self.current_href = href
                self.link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in self.DISCARD_TAGS:
            if self.discard_depth > 0:
                self.discard_depth -= 1
            return

        if self.discard_depth > 0:
            return

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote"):
            self.pieces.append("\n")
        elif tag_lower == "pre":
            self.in_pre = False
            self.pieces.append("\n```\n\n")
        elif tag_lower == "code" and not self.in_pre:
            self.in_code = False
            self.pieces.append("`")
        elif tag_lower == "a" and self.current_href:
            text = "".join(self.link_text).strip()
            if text:
                # Link formatı
                self.pieces.append(f"[{text}]({self.current_href})")
            elif self.current_href:
                self.pieces.append(f"<{self.current_href}>")
            self.current_href = None
            self.link_text = []

    def handle_data(self, data: str) -> None:
        if self.discard_depth > 0:
            return

        if self.current_href is not None:
            self.link_text.append(data)
            return

        self.pieces.append(data)

    def get_markdown(self) -> str:
        raw_text = "".join(self.pieces)
        decoded = unescape(raw_text)

        # Boşluk ve satır normalizasyonu
        lines = [line.rstrip() for line in decoded.splitlines()]
        cleaned = "\n".join(lines)
        # Ardışık 3 veya daha fazla satır sonunu 2'ye indir
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def clean_html(html_content: str) -> str:
    """Verilen HTML metnini ayıklayıp temiz Markdown döndürür."""
    if not html_content:
        return ""

    parser = SimpleHtmlToMarkdown()
    parser.feed(html_content)
    return parser.get_markdown()


def fetch_and_clean_url(url: str, timeout: int = 15) -> tuple[bool, str]:
    """URL'den güvenli şekilde HTML indirip temiz Markdown döndürür."""
    safe, reason = validate_safe_url(url)
    if not safe:
        return False, f"Güvenlik kalkanı reddetti: {reason}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 RespectedBrain/1.4.2"
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw_bytes = response.read()
            html_text = raw_bytes.decode(charset, errors="replace")
            cleaned_md = clean_html(html_text)
            return True, cleaned_md
    except Exception as e:
        return False, f"Sayfa indirme hatası: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Defuddle HTML temizleyici ve Markdown dönüştürücü")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="İndirilip temizlenecek URL")
    group.add_argument("--file", help="Temizlenecek yerel HTML dosyası")
    parser.add_argument("--output", help="Çıktının yazılacağı dosya yolu (varsayılan: stdout)")

    args = parser.parse_args()

    if args.url:
        ok, result = fetch_and_clean_url(args.url)
        if not ok:
            print(f"HATA: {result}", file=sys.stderr)
            return 1
        output_text = result
    else:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                output_text = clean_html(f.read())
        except Exception as e:
            print(f"Dosya okuma hatası: {e}", file=sys.stderr)
            return 1

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"Temiz içerik yazıldı: {args.output}")
        except Exception as e:
            print(f"Yazma hatası: {e}", file=sys.stderr)
            return 1
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
