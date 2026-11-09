# Registo de evidências da demonstração

Preencher durante os testes. Os resultados abaixo não devem ser pré-assumidos.

| Requisito | Comando/cenário | Esperado | Observado (preencher) | Responsável/data |
|---|---|---|---|---|
| TLS 1.3 e identidade servidor | `python tls_probe.py <URL>` | TLS 1.3, cipher, subject/SAN/serial corretos, HTTP 200 | Teste local: TLSv1.3, `TLS_AES_256_GCM_SHA384`, CN `coord`, SAN com `100.125.140.45` e `127.0.0.1`, serial `1004`; health HTTP 200 | 9 nov 2026 |
| mTLS positivo | `python client.py` | HTTP 201 | Teste local: HTTP 201 com Team A; o grupo também reportou envio Team A HTTP 201 em rede Tailscale | 9 nov 2026 |
| Rejeição de replay | enviar duas vezes `--message-id guided-check-002` | 201 e depois 409 | Teste local: primeira resposta 201; segunda 409 (servidor registou duplicate) | 9 nov 2026 |
| Operação offline | `client.py --queue`, desligar endpoint, depois `client.py --sync` | fila fica pendente offline e é drenada após reconexão |  |  |
| Cliente sem certificado | ligação sem `load_cert_chain` | handshake falha |  |  |
| Revogação | revogar, redistribuir CRL e reiniciar | certificado antigo rejeitado |  |  |
| AES round-trip | cifrar/decifrar `data/demo.txt` | ficheiro recuperado igual ao original |  |  |
| Backup e transferência cifrada | cifrar amostra, PUT e GET com `file_transfer.py`, decifrar e comparar SHA-256 | HTTPS/mTLS nos dois sentidos; ficheiro recuperado igual | Teste local: PUT HTTP 201, GET HTTP 200; GCM decifrou e SHA-256 coincidiu | 9 nov 2026 |
| AES adulterado | alterar byte em `.enc` ou chave errada | falha da tag GCM |  |  |
| Assinatura | assinar e verificar ficheiro original | assinatura válida |  |  |
| Assinatura adulterada | verificar cópia modificada | assinatura inválida |  |  |
| Password | Argon2id hash e verificação | correta aceita, errada rejeitada |  |  |
| Cofre | ler com política e sem política, depois rotacionar | permitido, negado, nova versão legível |  |  |

Não anexar tokens, passwords, chaves privadas, conteúdo de segredos ou dados pessoais às capturas.
