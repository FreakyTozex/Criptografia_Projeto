# PoC de Criptografia Aplicada

Esqueleto distribuído para uma demonstração académica com três computadores e containers Docker. Todos os dados são sintéticos. A configuração é apenas para laboratório; não usar em produção.

## Papéis sugeridos

- **Membro 1 — Centro de Coordenação:** API HTTPS/mTLS e OpenBao (cofre de segredos).
- **Membro 2 — Base Médica Principal:** API local HTTPS/mTLS para operações/sincronização.
- **Membro 3 — Equipas A e B:** containers clientes, ficheiros de teste cifrados e geração/verificação de assinaturas.

Cada computador usa o mesmo repositório, mas inicia apenas o(s) serviço(s) do seu papel. As redes Docker `bridge` são locais a cada PC; a ligação entre computadores usa o IP/hostname alcançável do host e portas publicadas.

## Requisitos

Docker Desktop com Compose v2; acesso de rede entre os PCs às portas TCP 8443 (Centro), 8444 (Base) e 8200 (OpenBao, apenas para o fluxo de segredos). Para a demonstração remota, prefiram uma VPN privada do grupo se a rede bloquear ligações diretas. TLS/mTLS continua obrigatório por cima da VPN.

## 1. Preparar a PKI de laboratório

Num único PC de administração, na raiz deste diretório:

```powershell
docker compose --profile tools run --rm pki-init
```

O script pergunta uma password para proteger a chave privada da Root CA. Guardem a Root CA offline e não a distribuam aos PCs. A CA intermédia assina certificados de `coord`, `base`, `team-a` e `team-b`; o bundle de confiança inclui Root, intermédia e CRL assinada.

Copiem para cada PC, por canal seguro, apenas:

- Centro: `certs/coord/` e `certs/ca/trust.pem`
- Base: `certs/base/` e `certs/ca/trust.pem`
- Equipa A: `certs/team-a/` e `certs/ca/root.crt` (e `intermediate.crt`, se validarem cadeia localmente)
- Equipa B: `certs/team-b/` e certificados de confiança

**Nunca copiem `certs/ca/root.key` para os PCs de execução nem o adicionem ao Git.** O script deixa a chave da intermédia no diretório de trabalho do administrador; protejam-na e mantenham-na fora dos PCs não autorizados. Em ambiente real, CAs devem ter armazenamento e controlo próprios.


### Se a criação da PKI parar com “Is a directory”

Isto costuma acontecer se algum serviço foi iniciado antes da PKI: o Compose pode criar pastas vazias para caminhos de certificados que ainda não existem. Pare os serviços e, na pasta do projeto, execute:

```powershell
docker compose down
docker compose --profile tools run --rm pki-resume
```

`pki-resume` só remove pastas vazias nos caminhos exatos dos ficheiros de certificado e retoma a emissão com a CA intermédia já criada. Se indicar que uma pasta tem conteúdo, pare e inspecione-a; não a apague automaticamente.
### Erro `PermissionError` ao carregar `server.key` ou `client.key`

A API e os clientes executam como utilizador sem privilégios. A nova imagem copia as chaves montadas para uma pasta privada dentro do container, ajusta o proprietário e inicia o processo como `poc`. Depois de atualizar os ficheiros, reconstrua e recrie os containers em cada PC:

```powershell
docker compose --profile coordinator up -d --build --force-recreate coordinator
docker compose --profile base up -d --build --force-recreate base
docker compose --profile team-a up -d --build --force-recreate team-a
docker compose --profile team-b up -d --build --force-recreate team-b
```

## 2. Configurar endereços

Copiem `.env.example` para `.env` em cada PC e preencham `COORD_IP` e `BASE_IP` com endereços alcançáveis a partir dos outros membros. Certificados de servidor são emitidos para DNS/IP indicados durante a emissão; se o IP mudar, voltem a emitir o certificado correspondente. Não usem `localhost` como endereço remoto.

Abram apenas as portas necessárias na firewall do host. Confirmem conectividade TCP entre os PCs antes da apresentação.

### Alteração do IP do Coordinator/Base

Se os IPs do `.env` foram corrigidos depois da emissão dos certificados, não execute `pki-init` outra vez. Reemita apenas os certificados TLS dos servidores pela CA existente:

```powershell
docker compose --profile tools run --rm pki-reissue-servers
```

O script usa `COORD_IP` e `BASE_IP` do `.env`, revoga os certificados de servidor anteriores e atualiza a CRL e `certs/ca/trust.pem`. Distribua o `trust.pem` atualizado a todos os PCs e recrie os serviços Coordinator e Base com `--build --force-recreate`.
## 3. Iniciar serviços por papel

Centro:

```powershell
docker compose --profile coordinator up -d coordinator openbao
```

Base:

```powershell
docker compose --profile base up -d base
```

Equipa A e B (no PC do terceiro membro, ou em PCs separados):

```powershell
docker compose --profile team-a up -d team-a
docker compose --profile team-b up -d team-b
```

Os containers de equipa ficam disponíveis para comandos `docker compose exec`. Endpoints: `https://COORD_IP:8443` e `https://BASE_IP:8444`. O cliente valida o nome/IP contra o certificado e apresenta certificado de cliente (mTLS).

## 4. Demonstração de mTLS e proteção contra repetição

A partir do container Team A, enviar mensagem sintética ao Centro (configure `TARGET_URL` no `.env`):

```powershell
docker compose exec team-a python client.py
```

A API aceita `POST /messages` com `message_id` único e rejeita um ID repetido (HTTP 409). A memória anti-repetição é volátil e reinicia com o serviço; num sistema real, guardem os IDs em armazenamento durável. Para provar a autenticação, tente sem certificado de cliente ou com certificado de outra CA; o handshake deve falhar. `GET /health` também exige mTLS.

A API requer TLS 1.3 e verifica a CRL assinada no handshake. Após revogar um certificado, reiniciem os serviços para carregar o bundle CRL atualizado.

## 5. Testar revogação

No PC administrador com a CA intermédia disponível:

```powershell
docker compose --profile tools run --rm pki-revoke team-a
```

Distribuam o novo `certs/ca/trust.pem` aos servidores (Centro/Base) por canal controlado e reiniciem-nos. A equipa revogada deve falhar durante o handshake TLS. Para voltar a testar, emitir um novo certificado com identidade nova; não reutilizar a chave comprometida.

## 6. Dados em repouso, assinatura e passwords

A imagem `poc-node` inclui `crypto_tools.py`:

```powershell
# Gerar uma chave aleatória e cifrar um ficheiro AES-256-GCM
docker compose exec team-a python crypto_tools.py keygen /data/aes.key
docker compose exec team-a python crypto_tools.py encrypt /data/demo.txt /data/demo.enc /data/aes.key
docker compose exec team-a python crypto_tools.py decrypt /data/demo.enc /data/recovered.txt /data/aes.key

# Hash de password para demonstração com Argon2id
docker compose exec team-a python crypto_tools.py password-hash
```

A chave de cifragem é separada do ficheiro apenas para a demonstração. Em utilização real, protejam a chave com KMS/TPM/cofre e controlo de acesso. Para assinar documentos, criem uma chave RSA-3072 separada das chaves TLS: `docker compose exec team-a python crypto_tools.py sign-keygen /data/signing-private.pem /data/signing-public.pem`; depois `... sign /data/demo.txt /data/demo.sig /data/signing-private.pem` e `... verify /data/demo.txt /data/demo.sig /data/signing-public.pem`. Alterem uma cópia do documento e repitam a verificação: deve falhar. A chave privada de demonstração não está cifrada, por isso mantenham-na apenas no container/ambiente de laboratório.

## 7. Cofre OpenBao

OpenBao inicia em modo **dev**, com token de laboratório definido em `.env.example`; serve apenas para demonstrar guardar/ler um segredo. Não exponham a porta 8200 à Internet, troquem o token e destruam o estado depois da apresentação. Para simular rotação, substituam o valor e confirmem que o consumidor passa a usar o novo segredo; o antigo deve deixar de ser aceite pela aplicação simulada.

## 8. Desconexão e incidente do portátil

1. Antes de desligar a rede, confirmem que cadeia e CRL estão distribuídas e que a API local continua acessível.
2. Bloqueiem temporariamente o acesso externo: operações locais podem continuar, sincronização remota não.
3. Expliquem que CRL em cache não sabe de uma revogação emitida depois da desconexão.
4. Incidente: revogar certificado Team A, trocar os segredos acessíveis, parar a sessão, emitir identidade nova para equipamento substituto e verificar que o certificado antigo falha após atualização da CRL.
5. Distingam dados cifrados com o equipamento desligado de dados potencialmente acessíveis com uma sessão já aberta.

## Estrutura

- `compose.yml`: papéis e portas publicados.
- `service/`: API TLS 1.3/mTLS, cliente com fila offline, transferência HTTPS cifrada, diagnóstico TLS e utilitários criptográficos.
- `scripts/`: inicialização, retomada, reemissão, revogação e emissão de certificados cliente com OpenSSL; `build-report.py` gera a versão DOCX do relatório.
- `data/`: ficheiros sintéticos; nunca colocar dados reais.

## Artefactos finais e alterações desta entrega

- `docs/relatorio-tecnico.md`: relatório orientado aos requisitos do enunciado, runbook de demonstração e resposta a portátil perdido.
- `docs/arquitetura.md`: diagrama Mermaid da arquitetura distribuída e limites de rede.
- `docs/matriz-criptografica.md`: algoritmos, parâmetros, justificação e limitações.
- `docs/evidencias.md`: tabela para registar resultados realmente observados na apresentação.
- `docs/openbao-demo.md`: passos para demonstrar leitura autorizada, negação e rotação no OpenBao.
- `Anexo_1_Analise_Guiada_Ameacas_preenchido.xlsx`: Anexo 1 preenchido.
- `Relatorio_Tecnico_PoC.docx`: versão Word do relatório técnico (gerada a partir do Markdown).

O servidor agora guarda IDs aceites em SQLite persistente no volume Docker `message_data`; repetir o mesmo `message_id` devolve HTTP 409 mesmo depois de reiniciar o processo. Cada cliente permite enfileirar mensagens sintéticas offline com `docker compose exec team-a python client.py --queue`, e sincronizar depois com `--sync`. O conteúdo da fila é cifrado com AES-GCM; o volume de chave de cada equipa é separado dos ficheiros em `/data`. Os volumes continuam locais a cada computador.

O cliente também verifica a CRL do certificado servidor. Para observar versão TLS, cipher, subject, SAN e serial do servidor:

```powershell
docker compose exec team-a python tls_probe.py
```

Para demonstrar uma cópia de segurança cifrada transferida por HTTPS/mTLS, siga os passos “Backup e transferência” no [relatório técnico](docs/relatorio-tecnico.md). O endpoint `/files/<nome>` só aceita ficheiros `POC1` (ficheiros produzidos pela cifra AES-GCM da PoC) até 5 MiB.

Pode fixar o ID da mensagem para testar replay: execute duas vezes `docker compose exec team-a python client.py --message-id demo-replay-001`; espera-se HTTP 201 e depois 409. Para emitir uma identidade nova para substituição de um portátil, na máquina administradora da CA:

```powershell
docker compose --profile tools run --rm pki-issue-client team-a-replacement
```

Após revogar `team-a`, distribua a CRL/bundle atualizados a Coordinator e Base e reinicie os servidores. Para uma demonstração segura, altere temporariamente os mounts do serviço Team A para os ficheiros da identidade `team-a-replacement`; não reutilize a chave do dispositivo perdido.

## Revisão antes da entrega

As instruções e capturas de execução em `docs/evidencias.md` devem ser completadas pelo grupo com saídas reais. Foi observado anteriormente um envio Team A com HTTP 201; os restantes casos indicados na tabela são resultados esperados e ainda requerem demonstração. Verifiquem também o .env em cada computador, o IP Tailscale presente no SAN, o estado TCP da porta e o relógio dos hosts antes da apresentação.

## Limites desta PoC

A aplicação, os segredos, a PKI e o OpenBao estão configurados para demonstração. Não há alta disponibilidade, gestão real de pacientes, hardening de produção, identidade federada nem proteção de endpoint. A CRL é carregada no arranque da API, pelo que precisa de distribuição e reinício para atualizar. Documentem sempre o resultado efetivamente observado nos vossos PCs.
