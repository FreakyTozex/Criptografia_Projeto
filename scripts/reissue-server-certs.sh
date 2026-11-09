#!/bin/sh
# Reemite os certificados TLS de coord e base com os IPs definidos em .env.
set -eu
cd /work
: "${COORD_IP:?Defina COORD_IP em .env}"
: "${BASE_IP:?Defina BASE_IP em .env}"
CONFIG=certs/ca/intermediate/openssl.cnf
[ -f "$CONFIG" ] && [ -f certs/ca/intermediate.key ] || { echo 'CA interm?dia/chave n?o encontrada neste host.'; exit 2; }
validate_ipv4() {
  printf '%s\n' "$1" | awk -F. 'NF!=4 {exit 1} {for(i=1;i<=4;i++) if($i !~ /^[0-9]+$/ || $i<0 || $i>255) exit 1}'
}
validate_ipv4 "$COORD_IP" || { echo 'COORD_IP inv?lido.'; exit 2; }
validate_ipv4 "$BASE_IP" || { echo 'BASE_IP inv?lido.'; exit 2; }
reissue() {
  name="$1"; ip="$2"; dir="certs/$name"; old="$dir/server.crt"; new="$dir/server.new.crt"
  [ -f "$old" ] && [ -f "$dir/server.key" ] || { echo "Certificado/chave de $name n?o encontrados."; exit 2; }
  openssl req -new -key "$dir/server.key" -subj "/CN=$name" -addext "subjectAltName=DNS:$name,IP:$ip,IP:127.0.0.1" -out "$dir/server.csr"
  openssl ca -batch -config "$CONFIG" -extensions server_cert -in "$dir/server.csr" -out "$new" -notext
  openssl ca -batch -config "$CONFIG" -revoke "$old"
  mv -f "$new" "$old"
}
reissue coord "$COORD_IP"
reissue base "$BASE_IP"
openssl ca -gencrl -config "$CONFIG" -out certs/ca/intermediate.crl
cat certs/ca/root.crt certs/ca/intermediate.crt certs/ca/intermediate.crl > certs/ca/trust.pem
chmod 600 certs/coord/server.key certs/base/server.key certs/ca/intermediate.key
rm -f certs/coord/server.csr certs/base/server.csr
printf 'Certificados do Coordinator e da Base reemitidos; certificados anteriores revogados. Distribua trust.pem atualizado.\n'
