#!/bin/sh
set -eu
cd /work
name=${1:-}
case "$name" in team-a|team-b|team-a-replacement|team-b-replacement) cert="certs/$name/client.crt";; *) echo 'Uso: pki-revoke team-a|team-b|team-a-replacement|team-b-replacement'; exit 2;; esac
[ -f "$cert" ] || { echo "Certificado nao encontrado: $cert"; exit 2; }
openssl ca -batch -config certs/ca/intermediate/openssl.cnf -revoke "$cert"
openssl ca -gencrl -config certs/ca/intermediate/openssl.cnf -out certs/ca/intermediate.crl
cat certs/ca/root.crt certs/ca/intermediate.crt certs/ca/intermediate.crl > certs/ca/trust.pem
printf 'Certificado revogado e CRL atualizada. Distribua trust.pem aos servidores e reinicie-os.\n'
