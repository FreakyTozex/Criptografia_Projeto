# Relatório técnico — PoC de Criptografia Aplicada

**Data:** 9 de novembro de 2026  
**Âmbito:** ambiente académico isolado, com dados inteiramente sintéticos.

## 1. Objetivo e cenário

A PoC representa um serviço de saúde distribuído por um Centro de Coordenação, uma Base Médica Principal e duas equipas. Os serviços correm em containers nos computadores dos três membros. A comunicação entre hosts usa a VPN Tailscale para endereçamento; TLS 1.3 e certificados continuam a proteger e autenticar cada ligação. O objetivo é demonstrar confidencialidade, integridade, autenticação, gestão de confiança, proteção em repouso e resposta a perda de um portátil, sem usar dados clínicos reais.

## 2. Componentes e fluxo de confiança

A PKI tem uma Root CA protegida por password e uma CA intermédia emissora. A Root deve permanecer offline. A intermédia emite folhas com RSA-2048 e validade de 90 dias; serviços recebem EKU `serverAuth`, clientes `clientAuth`. SAN do servidor deve conter o IP Tailscale (ou DNS) que o cliente efetivamente usa. Os clientes confiam no bundle `trust.pem`, que contém certificados da cadeia e CRL.

Coordinator aceita HTTPS na porta 8443 e Base na 8444. Ambos exigem certificado cliente (`CERT_REQUIRED`), TLS 1.3 e validação da CRL. O cliente valida a cadeia/nome/IP do servidor e também a CRL, além de apresentar a própria identidade. Tailscale transporta pacotes entre os hosts, mas não é assumida como substituta de autenticação criptográfica da aplicação.

## 3. Requisitos implementados

- **PKI:** geração da hierarquia e das identidades de servidor/equipa; reemissão dos certificados de servidor após troca de IP; revogação e emissão de identidade substituta.
- **TLS/mTLS:** os endpoints limitam o protocolo a TLS 1.3 e exigem certificados cliente. `tls_probe.py` apresenta parâmetros negociados e dados do certificado servidor observado.
- **Anti-repetição:** `message_id` é armazenado numa tabela SQLite com chave primária; o mesmo ID recebe HTTP 409 mesmo após reinício do serviço.
- **Continuidade offline:** cada cliente pode enfileirar mensagens sintéticas localmente; o conteúdo da fila usa AES-256-GCM com chave num volume Docker por equipa, separado da base SQLite. Ao recuperar rede, `--sync` tenta reenviar com o mesmo ID.
- **Criptografia em repouso:** AES-256-GCM cifra o ficheiro e autentica alterações; decifragem com chave errada ou conteúdo alterado falha.
- **Backup e transferência:** a API aceita e devolve apenas envelopes `POC1` cifrados, usando PUT/GET sob TLS 1.3 e mTLS. A equipa pode cifrar a amostra, transferi-la para o Coordinator e recuperá-la para confirmar a decifragem.
- **Integridade e assinatura:** RSA-PSS/SHA-256 assina o documento; verificação após alterar bytes deve falhar. A chave é separada da identidade TLS.
- **Passwords:** Argon2id, custo `3`, 64 MiB de memória, paralelismo `2`; salt único e parâmetros ficam codificados no hash PHC. O utilitário permite hashing/verificação.
- **Segredos:** OpenBao KV v2 é usado para demonstrar ciclo guardar/ler/autorizar/rodar. A execução dev deve ser apresentada apenas com valores descartáveis; os comandos e observações devem ser registados durante a demonstração.
- **Incidente:** revogar certificado da equipa, redistribuir CRL, reiniciar serviços, confirmar falha da identidade antiga, rodar segredos acessíveis e emitir chave/certificado para equipamento substituto.

## 4. Comandos de demonstração

Executar na raiz do projeto. Primeiro confirmar que os perfis e certificados correspondem aos IPs atuais:

```powershell
docker compose --profile coordinator up -d --build coordinator openbao
docker compose --profile base up -d --build base
docker compose --profile team-a up -d --build team-a
docker compose --profile team-b up -d --build team-b
```

Handshake, certificado e healthcheck, a partir de um container cliente:

```powershell
docker compose exec team-a python tls_probe.py
docker compose exec team-a python client.py
```

Repetir o mesmo identificador deve aceitar a primeira mensagem (201) e rejeitar a segunda (409):

```powershell
docker compose exec team-a python client.py --message-id demo-replay-001
docker compose exec team-a python client.py --message-id demo-replay-001
```

Para demonstrar continuidade local, enfileire enquanto o endpoint está inacessível e sincronize depois da rede voltar:

```powershell
docker compose exec team-a python client.py --queue --message-id offline-demo-001
# Restaurar conectividade Tailscale/serviço e depois:
docker compose exec team-a python client.py --sync
```

O conteúdo fica cifrado localmente e é removido da fila após HTTP 201 ou 409. A fila e a sua chave são locais ao host; não há sincronização entre hosts antes do envio.

Ficheiro e assinatura (usar apenas a amostra `data/demo.txt`):

```powershell
docker compose exec team-a python crypto_tools.py keygen /keys/demo.aes
docker compose exec team-a python crypto_tools.py encrypt /data/demo.txt /data/demo.enc /keys/demo.aes
docker compose exec team-a python crypto_tools.py decrypt /data/demo.enc /data/recovered.txt /keys/demo.aes
docker compose exec team-a python crypto_tools.py sign-keygen /keys/signing-private.pem /keys/signing-public.pem
docker compose exec team-a python crypto_tools.py sign /data/demo.txt /data/demo.sig /keys/signing-private.pem
docker compose exec team-a python crypto_tools.py verify /data/demo.txt /data/demo.sig /keys/signing-public.pem
```

Para provar adulteração, criar uma cópia alterada do ficheiro e executar `verify` contra essa cópia: o comando deve sair com erro. Para Argon2id executar `password-hash`, guardar o hash de demonstração temporariamente e validar com `password-verify <hash>`; nunca colocar uma password real nos argumentos/comandos.

Para simular backup/recuperação e transferência protegida, a API só guarda ficheiros que começam pelo formato cifrado da PoC. Isto demonstra TLS/mTLS em trânsito e AES-GCM em repouso:

```powershell
docker compose exec team-a python crypto_tools.py encrypt /data/demo.txt /data/demo-backup.enc /keys/demo.aes
docker compose exec team-a python file_transfer.py upload /data/demo-backup.enc
docker compose exec team-a python file_transfer.py download /data/recovered-backup.enc --name demo-backup.enc
docker compose exec team-a python crypto_tools.py decrypt /data/recovered-backup.enc /data/recovered-backup.txt /keys/demo.aes
Get-FileHash .\data\demo.txt -Algorithm SHA256
Get-FileHash .\data\recovered-backup.txt -Algorithm SHA256
```

Comparar o hash SHA-256 de `data/demo.txt` e do ficheiro recuperado. Para uma recuperação após perda de host, o grupo deve ainda demonstrar que consegue restaurar a cópia de segurança e obter a chave no processo autorizado; os volumes locais desta PoC não substituem um backup externo.

Revogação e renovação (na máquina administradora da CA):

```powershell
docker compose --profile tools run --rm pki-revoke team-a
# Distribuir trust.pem atualizado ao Coordinator e Base; reiniciá-los.
docker compose restart coordinator base
# Emitir uma nova identidade, com chave nova.
docker compose --profile tools run --rm pki-issue-client team-a-replacement
```

Para o teste de revogação, instale temporariamente o certificado revogado no container Team A e confirme que o handshake falha; depois restaure a nova identidade. Não substitua arquivos privados de produção nem distribua chaves da CA.

## 5. Gestão de segredos com OpenBao

O container atual inicia OpenBao em modo dev com root token local e porta ligada ao loopback. Isso facilita uma demonstração no host do Coordinator, mas não implementa um cofre de produção. Na apresentação, registem quatro resultados: (1) criar KV v2 e gravar um segredo descartável; (2) ler com token/política autorizada; (3) tentar ler com token sem política e mostrar rejeição; (4) substituir a versão do segredo e confirmar que o consumidor recebe o valor novo. Não imprimir o valor/token no relatório. Para produção: storage persistente selado, TLS, autenticação individual, políticas mínimas, auditoria e rotação de tokens.

## 6. Portátil perdido ou comprometido

1. Revogar o certificado cliente associado e publicar a CRL atualizada.
2. Distribuir o bundle de confiança revisto aos serviços e reiniciá-los; bloquear o dispositivo na Tailscale e invalidar sessões/tokens.
3. Rodar todos os segredos que o portátil podia ler; a revogação do certificado não revoga automaticamente tokens de aplicações.
4. Emitir uma chave privada nova e certificado novo para o equipamento substituto; nunca reutilizar a chave antiga.
5. Avaliar dados locais: AES-GCM protege ficheiros apenas se a chave também não estiver acessível ao atacante. Se ficheiro e chave residem juntos/desbloqueados, assumir exposição.
6. Limite de rede offline: serviços com CRL antiga podem ainda aceitar uma identidade revogada depois da última sincronização; reduza a janela com expiração curta, distribuição urgente da CRL e bloqueio de rede/conta.

## 7. Limitações e próximos passos para cenário real

OpenBao dev não tem TLS nem persistência segura; chaves AES, da fila offline e de assinatura ficam em volumes demonstrativos; SQLite de cada servidor contém apenas IDs; CRL é atualizada manualmente e só carregada no arranque; a fila é local por equipa e guarda apenas mensagens sintéticas; o endpoint de ficheiros não valida o tag GCM no servidor e não é backup externo automatizado; a API não guarda dados médicos nem implementa autorização por papel, auditoria inviolável, alta disponibilidade ou proteção de endpoints. Para operação real, usar KMS/HSM ou vault com políticas, backups cifrados/testados, gestão de identidade e papéis, armazenamento persistente seguro, monitorização, processo de resposta a incidentes e validação legal/clínica. A presente PoC não é apropriada a dados reais.

## 8. Evidência a recolher na apresentação

As saídas anteriores são resultados esperados, não resultados medidos neste documento. Durante a demo, guardar capturas/logs com data para: versão/cipher/SAN do `tls_probe`; resposta 201 e 409; rejeição sem certificado e após revogação; round-trip AES com comparação de hashes; verificação de assinatura antes/depois de alteração; formato e verificação Argon2id; leitura autorizada/negada e rotação no OpenBao. Preencher a coluna de resultado no registo `docs/evidencias.md` apenas com o observado.
