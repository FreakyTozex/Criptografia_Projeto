#!/bin/sh
set -eu
cd /work
if [ -e certs/ca/root.key ]; then echo 'PKI ja existe. Remova certs/ para recriar (isso revoga/descarta esta PKI).'; exit 2; fi
mkdir -p certs/ca/intermediate/newcerts certs/coord certs/base certs/team-a certs/team-b
chmod 700 certs/ca certs/ca/intermediate
printf 'Password para proteger a chave Root CA: '; stty -echo; read ROOT_PASS; stty echo; printf '\n'
export ROOT_PASS
openssl genpkey -algorithm RSA -aes-256-cbc -pkeyopt rsa_keygen_bits:3072 -pass env:ROOT_PASS -out certs/ca/root.key
openssl req -new -x509 -key certs/ca/root.key -passin env:ROOT_PASS -sha256 -days 3650 -subj '/CN=PoC-Org-Root-CA' -addext 'basicConstraints=critical,CA:TRUE,pathlen:1' -addext 'keyUsage=critical,keyCertSign,cRLSign' -out certs/ca/root.crt
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out certs/ca/intermediate.key
openssl req -new -key certs/ca/intermediate.key -subj '/CN=PoC-Org-Issuing-CA' -out certs/ca/intermediate.csr
cat > certs/ca/intermediate.ext <<'EOF'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
openssl x509 -req -in certs/ca/intermediate.csr -CA certs/ca/root.crt -CAkey certs/ca/root.key -passin env:ROOT_PASS -CAcreateserial -days 1825 -sha256 -extfile certs/ca/intermediate.ext -out certs/ca/intermediate.crt
cat > certs/ca/intermediate/openssl.cnf <<'EOF'
[ ca ]
default_ca = CA_default
[ CA_default ]
dir = ./certs/ca/intermediate
database = $dir/index.txt
new_certs_dir = $dir/newcerts
certificate = $dir/intermediate.crt
private_key = $dir/intermediate.key
serial = $dir/serial
crlnumber = $dir/crlnumber
default_md = sha256
default_days = 90
default_crl_days = 7
policy = policy_loose
x509_extensions = client_cert
copy_extensions = copy
unique_subject = no
[ policy_loose ]
commonName = supplied
[ client_cert ]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = clientAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
[ server_cert ]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
EOF
cp certs/ca/intermediate.crt certs/ca/intermediate/intermediate.crt
cp certs/ca/intermediate.key certs/ca/intermediate/intermediate.key

: > certs/ca/intermediate/index.txt
echo 1000 > certs/ca/intermediate/serial
echo 1000 > certs/ca/intermediate/crlnumber
issue_server() {
  name="$1"; san="$2"; dir="certs/$name"; mkdir -p "$dir"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/server.key"
  openssl req -new -key "$dir/server.key" -subj "/CN=$name" -addext "subjectAltName=$san" -out "$dir/server.csr"
  openssl ca -batch -config certs/ca/intermediate/openssl.cnf -extensions server_cert -in "$dir/server.csr" -out "$dir/server.crt" -notext
  chmod 600 "$dir/server.key"
}
issue_client() {
  name="$1"; dir="certs/$name"; mkdir -p "$dir"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/client.key"
  openssl req -new -key "$dir/client.key" -subj "/CN=$name" -out "$dir/client.csr"
  openssl ca -batch -config certs/ca/intermediate/openssl.cnf -extensions client_cert -in "$dir/client.csr" -out "$dir/client.crt" -notext
  chmod 600 "$dir/client.key"
}
COORD_IP=${COORD_IP:-127.0.0.1}; BASE_IP=${BASE_IP:-127.0.0.1}
issue_server coord "DNS:coord,IP:$COORD_IP,IP:127.0.0.1"
issue_server base "DNS:base,IP:$BASE_IP,IP:127.0.0.1"
issue_client team-a
issue_client team-b
openssl ca -gencrl -config certs/ca/intermediate/openssl.cnf -out certs/ca/intermediate.crl
cat certs/ca/root.crt certs/ca/intermediate.crt certs/ca/intermediate.crl > certs/ca/trust.pem
chmod 600 certs/ca/root.key certs/ca/intermediate.key
rm -f certs/ca/intermediate.csr certs/ca/intermediate.ext certs/ca/intermediate.key.tmp certs/ca/intermediate.srl certs/ca/root.srl
unset ROOT_PASS
printf '\nPKI pronta. Mantenha root.key offline; nao distribua chaves das CAs. Distribua a cada host apenas a identidade desse host e trust.pem.\n'
