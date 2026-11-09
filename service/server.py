import http.server, json, os, ssl, sqlite3, threading, re, uuid
from pathlib import Path
from urllib.parse import urlparse, unquote

CERT=os.environ.get('CERT_FILE','/run/certs/server.crt')
KEY=os.environ.get('KEY_FILE','/run/certs/server.key')
TRUST=os.environ.get('TRUST_FILE','/run/certs/trust.pem')
PORT=int(os.environ.get('PORT','8443'))
DB=os.environ.get('MESSAGE_DB','/data/messages.sqlite3')
FILES_DIR=Path(os.environ.get('FILES_DIR','/data/transfers'))
lock=threading.Lock()

def initialize_db():
    os.makedirs(os.path.dirname(DB) or '.', exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS received_messages (message_id TEXT PRIMARY KEY, client_subject TEXT NOT NULL, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')

initialize_db()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if urlparse(self.path).path != '/messages': self.send_error(404); return
        cert=self.connection.getpeercert()
        if not cert: self.send_error(401,'mTLS client certificate required'); return
        try:
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            mid=str(body['message_id']); text=str(body['message'])
            if not mid or len(mid)>100 or len(text)>4000: raise ValueError()
        except Exception:
            self.reply(400, {'error':'expected JSON with message_id and message'}); return
        subject=json.dumps(cert.get('subject'))
        try:
            with lock, sqlite3.connect(DB) as conn:
                conn.execute('INSERT INTO received_messages(message_id,client_subject) VALUES (?,?)',(mid,subject))
        except sqlite3.IntegrityError:
            self.reply(409, {'error':'duplicate message_id rejected'}); return
        print(json.dumps({'event':'message_received','message_id':mid,'client_subject':cert.get('subject')}),flush=True)
        self.reply(201, {'accepted':True,'message_id':mid})
    def do_PUT(self):
        name=self.file_name()
        if name is None: self.send_error(400,'invalid file name'); return
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: self.send_error(400,'invalid content length'); return
        if size < 20 or size > 5*1024*1024: self.send_error(413,'file must be between 20 bytes and 5 MiB'); return
        payload=self.rfile.read(size)
        if len(payload)!=size or not payload.startswith(b'POC1'):
            self.send_error(400,'only complete POC1 encrypted files are accepted'); return
        FILES_DIR.mkdir(parents=True,exist_ok=True)
        dest=FILES_DIR/name
        temp=FILES_DIR/(name+'.'+uuid.uuid4().hex+'.uploading')
        temp.write_bytes(payload)
        os.replace(temp,dest)
        self.reply(201,{'stored':True,'name':name,'bytes':len(payload),'encrypted':True})
    def do_GET_file(self):
        name=self.file_name()
        if name is None: self.send_error(400,'invalid file name'); return
        path=FILES_DIR/name
        if not path.is_file(): self.send_error(404,'file not found'); return
        payload=path.read_bytes()
        self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def file_name(self):
        path=urlparse(self.path).path
        if not path.startswith('/files/'): return None
        name=unquote(path[len('/files/'):])
        return name if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',name) and name not in {'.','..'} else None
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith('/files/'):
            self.do_GET_file(); return
        if path != '/health': self.send_error(404); return
        self.reply(200, {'status':'ok','tls':'TLS 1.3','mtls':True})
    def reply(self,status,obj):
        data=json.dumps(obj).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,fmt,*args): print('%s %s'%(self.client_address[0],fmt%args),flush=True)

ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version=ssl.TLSVersion.TLSv1_3; ctx.maximum_version=ssl.TLSVersion.TLSv1_3
ctx.load_cert_chain(CERT,KEY); ctx.load_verify_locations(cafile=TRUST); ctx.verify_mode=ssl.CERT_REQUIRED
ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
server=http.server.ThreadingHTTPServer(('0.0.0.0',PORT),Handler)
server.socket=ctx.wrap_socket(server.socket,server_side=True)
print(f'Listening on 0.0.0.0:{PORT}; TLS 1.3 and client certificates required',flush=True)
server.serve_forever()
