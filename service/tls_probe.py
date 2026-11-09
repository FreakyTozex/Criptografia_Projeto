"""Mostra parâmetros TLS e a identidade do servidor observados pelo cliente."""
import argparse
import json
import os
import socket
import ssl
from urllib.parse import urlsplit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url", nargs="?", default=os.environ.get("TARGET_URL"), help="URL HTTPS; por omissão usa TARGET_URL")
parser.add_argument("--cert", default=os.environ.get("CLIENT_CERT", "/run/poc-certs/client.crt"))
parser.add_argument("--key", default=os.environ.get("CLIENT_KEY", "/run/poc-certs/client.key"))
parser.add_argument("--trust", default=os.environ.get("TRUST_FILE", "/run/poc-certs/trust.pem"))
args = parser.parse_args()
if not args.url:
    parser.error("indica uma URL ou define TARGET_URL")
target = urlsplit(args.url)
if target.scheme != "https" or not target.hostname:
    parser.error("indica uma URL https válida")
port = target.port or 443
ctx = ssl.create_default_context(cafile=args.trust)
ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_3
ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
ctx.load_cert_chain(args.cert, args.key)
with socket.create_connection((target.hostname, port), timeout=8) as raw:
    with ctx.wrap_socket(raw, server_hostname=target.hostname) as conn:
        cert = conn.getpeercert()
        print(json.dumps({"tls_version": conn.version(), "cipher": conn.cipher(),
                          "server_subject": cert.get("subject"),
                          "server_san": cert.get("subjectAltName"),
                          "server_serial": cert.get("serialNumber")}, indent=2))
        conn.sendall(f"GET /health HTTP/1.1\r\nHost: {target.hostname}\r\nConnection: close\r\n\r\n".encode())
        response = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            response += chunk
        print(response.decode("utf-8", errors="replace"))
