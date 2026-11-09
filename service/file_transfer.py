"""Transfere ficheiros cifrados usando TLS 1.3 e mTLS."""
import argparse
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["upload", "download"])
parser.add_argument("path", help="ficheiro local de origem ou destino")
parser.add_argument("--name", help="nome seguro apresentado no servidor; por omissão usa o nome local")
parser.add_argument("--url", default=os.environ.get("TARGET_URL", "https://100.125.140.45:8443"))
args = parser.parse_args()
name = args.name or Path(args.path).name
url = args.url.rstrip("/") + "/files/" + quote(name, safe="")
ctx = ssl.create_default_context(cafile=os.environ.get("TRUST_FILE", "/run/poc-certs/trust.pem"))
ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_3
ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
ctx.load_cert_chain(os.environ.get("CLIENT_CERT", "/run/poc-certs/client.crt"),
                    os.environ.get("CLIENT_KEY", "/run/poc-certs/client.key"))

if args.action == "upload":
    data = Path(args.path).read_bytes()
    if not data.startswith(b"POC1"):
        parser.error("cifra primeiro o ficheiro com crypto_tools.py encrypt; só se aceitam ficheiros POC1")
    request = urllib.request.Request(url, data=data,
        headers={"Content-Type": "application/octet-stream"}, method="PUT")
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=15) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.code, exc.read().decode(errors="replace"))
        raise SystemExit(1)
else:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, context=ctx, timeout=15) as response:
        data = response.read()
    if not data.startswith(b"POC1"):
        raise SystemExit("O servidor não devolveu um ficheiro cifrado válido")
    Path(args.path).write_bytes(data)
    print(f"Ficheiro cifrado recebido: {args.path} ({len(data)} bytes)")
