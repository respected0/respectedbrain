"""DNS pinning transport and SSRF hardening tests."""
from __future__ import annotations

import io
import socket
import ssl
import unittest
from unittest import mock
import urllib.parse

from respectedbrain.maintenance.ingestion.url_safety import (
    is_private_or_reserved_ip,
    resolve_safe_addresses,
    validate_safe_url,
)
from respectedbrain.maintenance.ingestion.defuddle import (
    fetch_and_clean_url,
    safe_fetch_url,
)


class DnsPinningAndTransportSecurityTest(unittest.TestCase):
    def test_mixed_ipv4_ipv6_dns_response_is_rejected(self):
        """When DNS returns a mixed set of public IPv4 and private/loopback IPv6, it must fail-closed."""
        fake_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 80, 0, 0)),
        ]
        with mock.patch("socket.getaddrinfo", return_value=fake_addrinfo):
            safe, ips, reason = resolve_safe_addresses("example.com", 80)
            self.assertFalse(safe)
            self.assertEqual(ips, [])
            self.assertIn("özel/yerel", reason.lower())

    def test_dns_rebinding_pins_verified_ip_and_does_not_re_resolve(self):
        """DNS resolution occurs once; the transport connects strictly to the pinned IP without re-querying DNS."""
        calls = []

        def mock_getaddrinfo(host, port, *args, **kwargs):
            calls.append(host)
            if len(calls) == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
            # If transport re-resolves DNS, return private IP to simulate rebinding attack
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

        connected_addresses = []

        def mock_create_connection(address, timeout=None, *args, **kwargs):
            connected_addresses.append(address)
            # Create a mock socket
            sock = mock.MagicMock(spec=socket.socket)
            sock.makefile.return_value = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 13\r\n\r\nHello World\n")
            return sock

        with mock.patch("socket.getaddrinfo", side_effect=mock_getaddrinfo), \
             mock.patch("socket.create_connection", side_effect=mock_create_connection):
            ok, content, headers = safe_fetch_url("http://example.com/test", timeout=5)
            self.assertTrue(ok)
            self.assertEqual(content, b"Hello World\n")
            # Must connect directly to 93.184.216.34 and never to 127.0.0.1
            self.assertEqual(connected_addresses, [("93.184.216.34", 80)])
            # getaddrinfo must have been called exactly once by the safe resolver
            self.assertEqual(len(calls), 1)

    def test_redirect_to_metadata_or_private_is_rejected(self):
        """Redirect to 169.254.169.254 or private IP must be aborted immediately."""
        def mock_getaddrinfo(host, port, *args, **kwargs):
            if host == "public-site.com":
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port))]

        def mock_create_connection(address, timeout=None, *args, **kwargs):
            sock = mock.MagicMock(spec=socket.socket)
            # Return redirect to cloud metadata
            sock.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 302 Found\r\nLocation: http://169.254.169.254/latest/meta-data/\r\nContent-Length: 0\r\n\r\n"
            )
            return sock

        with mock.patch("socket.getaddrinfo", side_effect=mock_getaddrinfo), \
             mock.patch("socket.create_connection", side_effect=mock_create_connection):
            ok, err_or_content, _ = safe_fetch_url("http://public-site.com/redirect", timeout=5)
            self.assertFalse(ok)
            self.assertIn("özel/yerel", err_or_content.lower())

    def test_tls_hostname_and_sni_and_host_header_preserved(self):
        """HTTPS transport connects to pinned IP but validates TLS against actual URL hostname."""
        wrapped_hostnames = []
        sent_requests = []

        class MockSSLSocket:
            def __init__(self, raw_sock):
                self.raw_sock = raw_sock
            def sendall(self, data):
                sent_requests.append(data)
            def send(self, data):
                sent_requests.append(data)
                return len(data)
            def makefile(self, *args, **kwargs):
                return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nValid")
            def close(self):
                pass

        mock_context = mock.MagicMock(spec=ssl.SSLContext)
        mock_context.check_hostname = True
        mock_context.verify_mode = ssl.CERT_REQUIRED

        def mock_wrap_socket(sock, server_hostname=None):
            wrapped_hostnames.append(server_hostname)
            return MockSSLSocket(sock)

        mock_context.wrap_socket.side_effect = mock_wrap_socket

        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
             mock.patch("socket.create_connection", return_value=mock.MagicMock(spec=socket.socket)), \
             mock.patch("ssl.create_default_context", return_value=mock_context):
            ok, content, _ = safe_fetch_url("https://secure.example.com/api", timeout=5, ssl_context=mock_context)
            self.assertTrue(ok)
            self.assertEqual(content, b"Valid")
            # Verify server_hostname (SNI) is the actual URL hostname
            self.assertEqual(wrapped_hostnames, ["secure.example.com"])

    def test_environment_proxy_cannot_bypass_safe_transport(self):
        """Setting HTTP_PROXY or HTTPS_PROXY in environment must not alter direct pinned connection."""
        connected_addresses = []

        def mock_create_connection(address, timeout=None, *args, **kwargs):
            connected_addresses.append(address)
            sock = mock.MagicMock(spec=socket.socket)
            sock.makefile.return_value = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            return sock

        with mock.patch.dict("os.environ", {"HTTP_PROXY": "http://evil-proxy:8080", "HTTPS_PROXY": "http://evil-proxy:8080"}), \
             mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]), \
             mock.patch("socket.create_connection", side_effect=mock_create_connection):
            ok, content, _ = safe_fetch_url("http://example.com/test", timeout=5)
            self.assertTrue(ok)
            # The connection went directly to the verified pinned IP, completely ignoring the proxy
            self.assertEqual(connected_addresses, [("93.184.216.34", 80)])

    def test_excessive_redirects_fail_closed(self):
        """Redirect loop or exceeding max_redirects must fail-closed."""
        def mock_create_connection(address, timeout=None, *args, **kwargs):
            sock = mock.MagicMock(spec=socket.socket)
            sock.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 302 Found\r\nLocation: http://example.com/loop\r\nContent-Length: 0\r\n\r\n"
            )
            return sock

        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]), \
             mock.patch("socket.create_connection", side_effect=mock_create_connection):
            ok, err, _ = safe_fetch_url("http://example.com/loop", timeout=5, max_redirects=3)
            self.assertFalse(ok)
            self.assertIn("yönlendirme", err.lower())

    def test_byte_limit_enforced_during_stream_read(self):
        """Responses exceeding max_bytes must abort and not buffer oversized content."""
        def mock_create_connection(address, timeout=None, *args, **kwargs):
            sock = mock.MagicMock(spec=socket.socket)
            large_body = b"A" * 2000
            sock.makefile.return_value = io.BytesIO(
                b"HTTP/1.1 200 OK\r\nContent-Length: 2000\r\n\r\n" + large_body
            )
            return sock

        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]), \
             mock.patch("socket.create_connection", side_effect=mock_create_connection):
            ok, err, _ = safe_fetch_url("http://example.com/large", timeout=5, max_bytes=500)
            self.assertFalse(ok)
            self.assertIn("boyut", err.lower())

    def test_slow_stream_overall_deadline_enforced(self):
        """A slow streaming response whose cumulative read duration exceeds overall deadline must abort."""
        elapsed = [0.0]

        class SlowResponse:
            status = 200
            def __init__(self, sock):
                self.chunks = [b"chunk1", b"chunk2", b"chunk3", b""]
            def begin(self):
                pass
            def getheaders(self):
                return []
            def read(self, size):
                elapsed[0] += 4.0
                return self.chunks.pop(0)

        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]), \
             mock.patch("socket.create_connection", return_value=mock.MagicMock()), \
             mock.patch("http.client.HTTPResponse", SlowResponse), \
             mock.patch("time.monotonic", side_effect=lambda: elapsed[0]):
            success, err, _ = safe_fetch_url("http://example.com/slow", timeout=5)
            self.assertFalse(success)
            self.assertIn("zaman aşımı", err.lower())

    def test_insecure_caller_ssl_context_rejected(self):
        """Caller-supplied SSL context with CERT_NONE or check_hostname=False must be rejected fail-closed."""
        bad_context = mock.MagicMock(spec=ssl.SSLContext)
        bad_context.verify_mode = ssl.CERT_NONE
        bad_context.check_hostname = False

        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
             mock.patch("socket.create_connection", return_value=mock.MagicMock()):
            ok, err, _ = safe_fetch_url("https://example.com/api", timeout=5, ssl_context=bad_context)
            self.assertFalse(ok)
            self.assertIn("güvenli olmayan ssl", err.lower())

    def test_host_header_ipv6_and_custom_port(self):
        """IPv6 literal addresses must be formatted as [addr] in Host header, and non-80/443 ports must be rejected."""
        # Non-standard port 8443 must be rejected by URL safety
        ok_unsafe, err_unsafe, _ = safe_fetch_url("https://[2606:2800:220:1:248:1893:25c8:1946]:8443/test", timeout=5)
        self.assertFalse(ok_unsafe)
        self.assertIn("güvensiz port", err_unsafe.lower())

        # Standard port 443 with IPv6 literal must produce [addr] Host header
        sent_data = []

        class MockSocket:
            def sendall(self, data):
                sent_data.append(data)
            def settimeout(self, timeout):
                pass
            def close(self):
                pass

        class MockResponse:
            status = 200
            def begin(self):
                pass
            def getheaders(self):
                return []
            def read(self, size):
                return b""

        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0))]), \
             mock.patch("socket.create_connection", return_value=MockSocket()), \
             mock.patch("ssl.create_default_context", return_value=mock.MagicMock(wrap_socket=lambda s, server_hostname: s)), \
             mock.patch("http.client.HTTPResponse", lambda s: MockResponse()):
            ok, _, _ = safe_fetch_url("https://[2606:2800:220:1:248:1893:25c8:1946]/test", timeout=5)
            self.assertTrue(ok)
            raw_req = b"".join(sent_data).decode("iso-8859-1")
            self.assertIn("Host: [2606:2800:220:1:248:1893:25c8:1946]", raw_req)



if __name__ == "__main__":
    unittest.main()

