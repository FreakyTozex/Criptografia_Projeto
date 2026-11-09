"""Cliente mTLS com fila local e sincronização idempotente de mensagens sintéticas."""
import argparse
import json
import os
import sqlite3
import ssl
import secrets
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--message-id", help="ID fixo para demonstrar deduplicação")
parser.add_argument("--url", default=os.environ.get("TARGET_URL", "https://100.125.140.45:8443"))
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--queue", action="store_true", help="guarda mensagem localmente sem rede")
mode.add_argument("--sync", action="store_true", help="envia mensagens pendentes da fila local")
args = parser.parse_args()

db_file = os.environ.get("OUTBOX_DB", "/data/outbox.sqlite3")
key_file = Path(os.environ.get("OUTBOX_KEY", "/keys/outbox.key"))

def open_db():
    os.makedirs(os.path.dirname(db_file) or ".", exist_ok=True)
    db = sqlite3.connect(db_file)
    db.execute("CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message BLOB NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    return db

def get_outbox_key():
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key_file.exists():
        key_file.write_bytes(secrets.token_bytes(32))
        key_file.chmod(0o600)
    key = key_file.read_bytes()
    if len(key) != 32:
        raise RuntimeError("Chave da fila local inválida")
    return key

def queue_message(mid):
    message = "relatorio-sintetico: consulta concluida"
    nonce = secrets.token_bytes(12)
    encrypted = nonce + AESGCM(get_outbox_key()).encrypt(nonce, message.encode(), mid.encode())
    with open_db() as db:
        db.execute("INSERT OR IGNORE INTO outbox(message_id,message) VALUES (?,?)", (mid, encrypted))
    print(json.dumps({"queued": True, "message_id": mid}))

def make_context():
    ctx = ssl.create_default_context(cafile=os.environ.get("TRUST_FILE", "/run/poc-certs/trust.pem"))
    ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
    ctx.load_cert_chain(os.environ.get("CLIENT_CERT", "/run/poc-certs/client.crt"),
                        os.environ.get("CLIENT_KEY", "/run/poc-certs/client.key"))
    return ctx

def send(mid, message, ctx):
    url = args.url.rstrip("/") + "/messages"
    payload = json.dumps({"message_id": mid, "message": message}).encode()
    req = urllib.request.Request(url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
            print(response.status, response.read().decode())
            return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 409:
            print(exc.code, detail)
            return True
        print(exc.code, detail)
        return False
    except urllib.error.URLError as exc:
        print(json.dumps({"queued_offline": True, "message_id": mid, "reason": str(exc.reason)}))
        return False

if args.queue:
    queue_message(args.message_id or str(uuid.uuid4()))
elif args.sync:
    ctx = make_context()
    key = get_outbox_key()
    with open_db() as db:
        pending = db.execute("SELECT message_id,message FROM outbox ORDER BY created_at,message_id").fetchall()
        for mid, encrypted in pending:
            nonce, ciphertext = encrypted[:12], encrypted[12:]
            message = AESGCM(key).decrypt(nonce, ciphertext, mid.encode()).decode()
            if send(mid, message, ctx):
                db.execute("DELETE FROM outbox WHERE message_id=?", (mid,))
            else:
                print("Sincronização interrompida; as mensagens pendentes continuam na fila.")
                break
    with open_db() as db:
        count = db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    print(json.dumps({"pending": count}))
else:
    send(args.message_id or str(uuid.uuid4()), "relatorio-sintetico: consulta concluida", make_context())
