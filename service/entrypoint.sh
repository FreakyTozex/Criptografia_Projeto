#!/bin/sh
set -eu
src=/run/certs
dst=/run/poc-certs
mkdir -p "$dst"
for name in server.crt server.key client.crt client.key trust.pem; do
  if [ -f "$src/$name" ]; then cp "$src/$name" "$dst/$name"; fi
done
[ -f "$dst/trust.pem" ] || { echo 'trust.pem em falta em /run/certs'; exit 1; }
chown -R poc:poc "$dst"
for key in "$dst"/*.key; do
  [ -f "$key" ] && chmod 600 "$key"
done
for cert in "$dst"/*.crt "$dst"/trust.pem; do
  [ -f "$cert" ] && chmod 644 "$cert"
done
exec gosu poc "$@"
