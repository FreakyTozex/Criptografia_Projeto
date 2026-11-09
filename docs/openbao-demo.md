# Demonstração do ciclo de segredo no OpenBao

Executar no host Coordinator depois de `docker compose --profile coordinator up -d openbao`. Use apenas um valor fictício. O modo dev não tem persistência nem TLS, e o root token é de laboratório.

## PowerShell

O Compose fornece o endereço e o token de laboratório dentro do container `openbao`. Não mostrar os valores do `.env` durante a gravação do ecrã. Ativar um mount KV v2 dedicado (executar uma vez por arranque do modo dev), gravar e ler um segredo fictício:

```powershell
docker compose exec openbao bao secrets enable -path=poc kv-v2
docker compose exec openbao bao kv put poc/demo api_key='demo-v1'
docker compose exec openbao bao kv get poc/demo
```

Criar política read-only, emitir token temporário, validar leitura autorizada e negar escrita:

```powershell
$policy = @'
path "poc/data/*" {
  capabilities = ["read"]
}
'@
$policy | docker compose exec -T openbao bao policy write poc-reader -
$readToken = docker compose exec openbao bao token create -policy=poc-reader -period=15m -field=token
docker compose exec -e BAO_TOKEN=$readToken openbao bao kv get poc/demo
docker compose exec -e BAO_TOKEN=$readToken openbao bao kv put poc/demo api_key='must-fail'
```

O `get` deve funcionar e o `put` deve devolver erro de autorização. Rodar o valor com o root token e ler novamente usando o token temporário:

```powershell
docker compose exec openbao bao kv put poc/demo api_key='demo-v2'
docker compose exec -e BAO_TOKEN=$readToken openbao bao kv get poc/demo
```

A leitura mostra a nova versão (`demo-v2`). O token de leitura não vê qualquer valor fora de `secret/poc/*`, não pode escrever e expira ao fim de 15 minutos. No final, remover as variáveis da sessão PowerShell:

```powershell
Remove-Variable readToken
```

## Registo da evidência

Guardar apenas o código de saída e resultado (permitido/negado/versão incrementada). Não guardar tokens nem valores secretos. Como o serviço está em modo dev, reiniciar o container apaga o estado e será necessário repetir a configuração.
