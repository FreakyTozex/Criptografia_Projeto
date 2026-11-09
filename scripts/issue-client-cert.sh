#!/bin/sh
set -eu
cd /work
name=${1:-}
case "$name" in team-a|team-b|team-a-replacement|team-b-replacement) ;; *) echo 'Uso: pki-issue-client team-a|team-b|team-a-replacement|team-b-replacement'; exit 2;; esac
dir="certs/$name"
[ ! -e "$dir/client.key" ] || { echo "Identidade ja existe: $dir"; exit 2; }
[ -f certs/ca/intermediate.key ] || { echo 'Chave da CA intermédia indisponivel neste host'; exit 2; }
mkdir -p "$dir"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$dir/client.key"
openssl req -new -key "$dir/client.key" -subj "/CN=$name" -out "$dir/client.csr"
openssl ca -batch -config certs/ca/intermediate/openssl.cnf -extensions client_cert -in "$dir/client.csr" -out "$dir/client.crt" -notext
chmod 600 "$dir/client.key"
rm -f "$dir/client.csr"
printf 'Identidade %s emitida. Distribua client.crt, client.key por canal seguro e trust.pem atualizado.\n' "$name"
