#!/bin/sh
# Recupera uma inicializacao que chegou a criar a CA mas falhou ao criar as folhas.
set -eu
cd /work
[ -f certs/ca/root.crt ] && [ -f certs/ca/intermediate.crt ] && [ -f certs/ca/intermediate.key ] || { echo 'CA parcial nao encontrada; use init-pki.sh.'; exit 2; }
[ -f certs/ca/intermediate/openssl.cnf ] && [ -f certs/ca/intermediate/index.txt ] && [ -f certs/ca/intermediate/serial ] || { echo 'Base da CA interm?dia incompleta; n?o continuar automaticamente.'; exit 2; }
# Docker Compose pode criar pastas vazias para bind mounts de ficheiros ainda inexistentes.
for path in certs/coord/server.crt certs/coord/server.key certs/base/server.crt certs/base/server.key certs/team-a/client.crt certs/team-a/client.key certs/team-b/client.crt certs/team-b/client.key certs/ca/trust.pem; do
  if [ -d "$path" ]; then
    if [ -z "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]; then rmdir "$path"; else echo "Esperava ficheiro mas encontrei pasta com conte?do: $path"; exit 2; fi
  fi
done
issue_server() {
  name="$1"; san="$2"; dir="certs/$name"; mkdir -p "$dir"
  [ -f "$dir/server.key" ] || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/server.key"
  [ -f "$dir/server.csr" ] || openssl req -new -key "$dir/server.key" -subj "/CN=$name" -addext "subjectAltName=$san" -out "$dir/server.csr"
  [ -f "$dir/server.crt" ] || openssl ca -batch -config certs/ca/intermediate/openssl.cnf -extensions server_cert -in "$dir/server.csr" -out "$dir/server.crt" -notext
  chmod 600 "$dir/server.key"
}
issue_client() {
  name="$1"; dir="certs/$name"; mkdir -p "$dir"
  [ -f "$dir/client.key" ] || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/client.key"
  [ -f "$dir/client.csr" ] || openssl req -new -key "$dir/client.key" -subj "/CN=$name" -out "$dir/client.csr"
  [ -f "$dir/client.crt" ] || openssl ca -batch -config certs/ca/intermediate/openssl.cnf -extensions client_cert -in "$dir/client.csr" -out "$dir/client.crt" -notext
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
printf 'PKI recuperada. Proteja as chaves privadas e distribua apenas o necess?rio.\n'
