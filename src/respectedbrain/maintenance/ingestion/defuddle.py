#!/usr/bin/env python3
"""Defuddle - Web Sayfası Gürültü Sıyırıcı ve Temiz Markdown Çıkarıcı.

HTML içeriklerindeki reklamları, gezinme menülerini, çerez bantlarını,
script ve stilleri temizleyerek LLM modelleri için saf, okunabilir ve
token-verimli Markdown metni üretir.
"""

from __future__ import annotations

from respectedbrain.core.context import AppContext
from respectedbrain.maintenance import mutable_target

import argparse
import concurrent.futures
from html import unescape
from html.parser import HTMLParser
import io
from pathlib import Path
import queue
import re
import sys
import threading
import time
from typing import Any
import urllib.request





from .url_safety import validate_safe_url


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


MAX_HTML_STRING_LEN = 10 * 1024 * 1024  # 10 MB karakter sınırı


def clean_html(html_content: str) -> str:
    """Verilen HTML metnini ayıklayıp temiz Markdown döndürür."""
    if not html_content:
        return ""

    if len(html_content) > MAX_HTML_STRING_LEN:
        html_content = html_content[:MAX_HTML_STRING_LEN]

    parser = SimpleHtmlToMarkdown()
    parser.feed(html_content)
    return parser.get_markdown()


MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5 MB tavan bellek sınırı
MAX_REDIRECTS = 5


class _ResolverPool:
    def __init__(self, workers: int = 2, queued: int = 2):
        self.work = queue.Queue(maxsize=queued)
        self.threads = tuple(
            threading.Thread(target=self._run, name=f'respectedbrain-resolver-{index + 1}', daemon=True)
            for index in range(workers)
        )
        for thread in self.threads:
            thread.start()

    def _run(self) -> None:
        while True:
            future, function, args, kwargs = self.work.get()
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(function(*args, **kwargs))
            except BaseException as error:
                future.set_exception(error)

    def submit(self, function, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            self.work.put_nowait((future, function, args, kwargs))
        except queue.Full:
            future.set_exception(RuntimeError('resolver-capacity-reached'))
        return future


_RESOLVER_POOL = _ResolverPool()


class _DeadlineReader(io.RawIOBase):
    def __init__(self, stream: Any, deadline: float, socket: Any = None):
        self.stream = stream
        self.deadline = deadline
        self.socket = socket

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('İstek zaman aşımına uğradı')
        if self.socket is not None and hasattr(self.socket, 'settimeout'):
            self.socket.settimeout(remaining)
        view = memoryview(buffer)
        result = self.stream.readinto(view) if hasattr(self.stream, 'readinto') else self.stream.read(len(view))
        self._check_deadline()
        if result is None:
            return 0
        if isinstance(result, bytes):
            view[:len(result)] = result
            return len(result)
        return result

    def _check_deadline(self) -> None:
        if time.monotonic() >= self.deadline:
            raise TimeoutError('İstek zaman aşımına uğradı')


class _DeadlineSocket:
    def __init__(self, sock: Any, deadline: float):
        self.sock = sock
        self.deadline = deadline

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('İstek zaman aşımına uğradı')
        return remaining

    def settimeout(self, timeout: float | None) -> None:
        remaining = self._remaining()
        if timeout is None or timeout > remaining:
            timeout = remaining
        self.sock.settimeout(timeout)

    def recv(self, size: int) -> bytes:
        remaining = self._remaining()
        if hasattr(self.sock, 'settimeout'):
            self.sock.settimeout(remaining)
        result = self.sock.recv(size)
        self._remaining()
        return result

    def recv_into(self, buffer: Any) -> int:
        remaining = self._remaining()
        if hasattr(self.sock, 'settimeout'):
            self.sock.settimeout(remaining)
        result = self.sock.recv_into(buffer)
        self._remaining()
        return result

    def sendall(self, data: bytes) -> None:
        remaining = self._remaining()
        if hasattr(self.sock, 'settimeout'):
            self.sock.settimeout(remaining)
        self.sock.sendall(data)
        self._remaining()

    def makefile(self, mode: str, *args: Any, **kwargs: Any) -> Any:
        stream = self.sock.makefile(mode, *args, **kwargs)
        return io.BufferedReader(_DeadlineReader(stream, self.deadline, self.sock), buffer_size=1)

    def close(self) -> None:
        self.sock.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.sock, name)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Geriye dönük uyumluluk için yönlendirme kalkanı."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        safe, reason = validate_safe_url(newurl, require_resolvable=True)
        if not safe:
            raise ValueError(f"Yönlendirme engellendi (güvenlik kalkanı): {reason}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_fetch_url(
    url: str,
    timeout: float = 15.0,
    max_bytes: int = MAX_FETCH_BYTES,
    max_redirects: int = MAX_REDIRECTS,
    ssl_context: Any = None,
) -> tuple[bool, Any, dict[str, str]]:
    """Doğrulanmış IP adresine doğrudan soket bağlayarak (DNS pinning) güvenli HTTP/HTTPS isteği yapar.

    DNS rebinding, SSRF, proxy bypass, yönlendirme döngüleri ve aşırı bellek tüketimini önler.
    Döndürür:
        (success: bool, content_bytes_or_error: bytes | str, headers: dict[str, str])
    """
    import http.client
    import socket
    import ssl
    import time
    from urllib.parse import urlsplit, urljoin
    from .url_safety import resolve_safe_addresses

    start_time = time.monotonic()
    current_url = url
    redirect_count = 0

    def _check_deadline() -> float:
        rem = timeout - (time.monotonic() - start_time)
        if rem <= 0:
            raise TimeoutError("İstek zaman aşımına uğradı")
        return rem

    while True:
        try:
            remaining_timeout = _check_deadline()
        except TimeoutError:
            return False, "İstek zaman aşımına uğradı", {}

        safe, reason = validate_safe_url(current_url, require_resolvable=False)
        if not safe:
            return False, f"Güvenlik kalkanı reddetti: {reason}", {}

        try:
            parsed = urlsplit(current_url)
        except Exception as e:
            return False, f"URL ayrıştırma hatası: {e}", {}

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Desteklenmeyen protokol: {scheme}", {}

        hostname = parsed.hostname
        if not hostname:
            return False, "Geçerli bir hostname bulunamadı", {}

        port = parsed.port or (443 if scheme == "https" else 80)

        # DNS çözümleme ve IP sabitleme (DNS pinning) ile toplam deadline denetimi
        rem_dns = _check_deadline()
        try:
            import concurrent.futures
            dns_future = _RESOLVER_POOL.submit(resolve_safe_addresses, hostname, port)
            safe_dns, safe_ips, dns_reason = dns_future.result(timeout=rem_dns)
        except (concurrent.futures.TimeoutError, TimeoutError):
            return False, "Bağlantı zaman aşımına uğradı", {}
        except Exception as e:
            return False, f"DNS çözümleme hatası: {e}", {}

        if not safe_dns or not safe_ips:
            return False, f"DNS çözümleme güvenlik reddi: {dns_reason}", {}

        pinned_ip = safe_ips[0]

        def _safe_set_sock_timeout(s: Any, t: float) -> None:
            if hasattr(s, "settimeout"):
                try:
                    s.settimeout(t)
                except OSError:
                    raise

        sock = None
        try:
            # Doğrudan doğrulanmış genel IP adresine bağlan (ortam proxy'sini atla, DNS rebinding'i önle)
            conn_timeout = _check_deadline()
            sock = socket.create_connection((pinned_ip, port), timeout=conn_timeout)

            # HTTPS için TLS el sıkışması
            if scheme == "https":
                ctx = ssl_context
                if ctx is None:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = True
                    ctx.verify_mode = ssl.CERT_REQUIRED
                else:
                    if getattr(ctx, "verify_mode", None) != ssl.CERT_REQUIRED or not getattr(ctx, "check_hostname", False):
                        return False, "Güvenli olmayan SSL bağlamı reddedildi: sertifika ve hostname doğrulaması zorunludur", {}
                rem_tls = _check_deadline()
                _safe_set_sock_timeout(sock, rem_tls)
                sock = ctx.wrap_socket(sock, server_hostname=hostname)

            # HTTP isteği gönder
            path_selector = parsed.path or "/"
            if parsed.query:
                path_selector = f"{path_selector}?{parsed.query}"

            # Host başlığı (orijinal hostname, IPv6 formatı ve standart/standart dışı port ayrımı)
            formatted_host = f"[{hostname.strip('[]')}]" if (":" in hostname) else hostname
            if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
                host_header = formatted_host
            else:
                host_header = f"{formatted_host}:{port}"

            req_lines = [
                f"GET {path_selector} HTTP/1.1",
                f"Host: {host_header}",
                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 RespectedBrain/0.0.1",
                "Accept-Encoding: identity",
                "Connection: close",
                "",
                "",
            ]
            req_data = "\r\n".join(req_lines).encode("iso-8859-1")
            rem_send = _check_deadline()
            _safe_set_sock_timeout(sock, rem_send)
            sock.sendall(req_data)

            # HTTP yanıtını işle
            rem_resp = _check_deadline()
            _safe_set_sock_timeout(sock, rem_resp)
            response = http.client.HTTPResponse(_DeadlineSocket(sock, start_time + timeout))
            response.begin()

            status = response.status
            headers = {k: v for k, v in response.getheaders()}

            # Yönlendirme (301, 302, 303, 307, 308)
            if status in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > max_redirects:
                    return False, f"Aşırı yönlendirme sınırı aşıldı ({max_redirects})", headers

                location = headers.get("Location") or headers.get("location")
                if not location:
                    return False, "Yönlendirme yanıtında Location başlığı eksik", headers

                current_url = urljoin(current_url, location)
                continue

            if status != 200:
                return False, f"Sunucu hata kodu döndürdü ({status})", headers

            # Yanıt gövdesini sınırlandırarak oku; her düşük seviyeli okumada ortak deadline'ı uygula
            buffer = bytearray()
            chunk_size = 65536
            while True:
                rem_timeout = _check_deadline()
                _safe_set_sock_timeout(sock, rem_timeout)
                remaining_bytes = max_bytes - len(buffer)
                if remaining_bytes < 0:
                    return False, f"Azami veri boyutu sınırı aşıldı ({max_bytes} bayt)", headers

                to_read = min(chunk_size, remaining_bytes + 1)
                chunk = response.read1(to_read) if hasattr(response, "read1") else response.read(to_read)
                _check_deadline()
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    return False, f"Azami veri boyutu sınırı aşıldı ({max_bytes} bayt)", headers

            _check_deadline()
            return True, bytes(buffer), headers

        except (socket.timeout, TimeoutError, concurrent.futures.TimeoutError):
            return False, "Bağlantı zaman aşımına uğradı", {}
        except Exception as e:
            return False, f"HTTP bağlantı hatası: {e}", {}
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass



def fetch_and_clean_url(url: str, timeout: int = 15, max_bytes: int = MAX_FETCH_BYTES) -> tuple[bool, str]:
    """URL'den güvenli şekilde (DNS pinning ve SSRF kalkanı ile) HTML indirip temiz Markdown döndürür."""
    ok, result_or_err, headers = safe_fetch_url(url, timeout=timeout, max_bytes=max_bytes)
    if not ok:
        return False, str(result_or_err)

    raw_bytes = result_or_err
    content_type = headers.get("Content-Type", "") or headers.get("content-type", "")
    charset = "utf-8"
    if "charset=" in content_type.lower():
        parts = content_type.lower().split("charset=")
        if len(parts) > 1:
            candidate = parts[1].split(";")[0].strip().strip('"\'')
            if candidate:
                charset = candidate

    try:
        html_text = raw_bytes.decode(charset, errors="replace")
    except Exception:
        html_text = raw_bytes.decode("utf-8", errors="replace")

    cleaned_md = clean_html(html_text)
    return True, cleaned_md


def main(argv=None, *, ctx: AppContext | None = None) -> int:
    parser = argparse.ArgumentParser(description="Defuddle HTML temizleyici ve Markdown dönüştürücü")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="İndirilip temizlenecek URL")
    group.add_argument("--file", help="Temizlenecek yerel HTML dosyası")
    parser.add_argument("--output", help="Çıktının yazılacağı dosya yolu (varsayılan: stdout)")

    args = parser.parse_args(argv)

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
        mutable_target(ctx, Path(args.output))
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
