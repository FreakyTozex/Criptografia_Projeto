# Matriz de decisões criptográficas

| Necessidade | Decisão nesta PoC | Parâmetros / evidência | Limite conhecido |
|---|---|---|---|
| Confiança organizacional | PKI privada hierárquica | Root RSA-3072 protegida por password; CA intermédia RSA-3072; folhas assinadas pela intermédia | Chave intermédia existe em ficheiro e precisa de proteção operacional reforçada |
| Transporte | TLS 1.3 | Contextos cliente/servidor limitados a TLS 1.3; validação de cadeia e nome/IP; `tls_probe.py` mostra versão, cipher, subject, SAN e serial | Tailscale dá conectividade; não substitui TLS nem revogação |
| Autenticação mútua | mTLS com `CERT_REQUIRED` | Certificados cliente e servidor com EKU adequado; teste com `client.py` | Autorização por função na aplicação ainda é mínima |
| Revogação | CRL X.509 assinada pela intermédia | CRL incluída em `trust.pem`; servidores e cliente ativam `VERIFY_CRL_CHECK_LEAF` | CRL é distribuída manualmente; serviços têm de reiniciar; sem OCSP |
| Dados em repouso | AES-256-GCM | Chave aleatória 256-bit; nonce 96-bit; tag de autenticação; volumes Docker separados `/data` e `/keys` | Volumes locais não são KMS/TPM e não protegem contra administrador/compromisso do host |
| Integridade/autoria | RSA-PSS + SHA-256 | Chave de assinatura RSA-3072 separada da chave TLS; alteração do documento invalida assinatura | Distribuição/confiança da chave pública é manual |
| Passwords | Argon2id | `time_cost=3`, `memory_cost=65536 KiB`, `parallelism=2`; salt aleatório incluído no formato PHC pela biblioteca | Demonstrativo; o custo deve ser medido e ajustado ao equipamento final |
| Cofre de segredos | OpenBao KV v2 | Demonstração de gravação, leitura autorizada, rejeição sem política e substituição do valor | Container dev, root token estático e sem TLS; não guardar segredos reais |
| Continuidade e repetição | Fila local cifrada + ID único com restrição SQLite | Conteúdo local cifrado com AES-256-GCM; reenvio mantém ID; servidor rejeita duplicado com HTTP 409 | Fila local por host/equipa, apenas mensagens sintéticas; sem sincronização transacional de registos clínicos |

## Justificação resumida

TLS 1.3 reduz opções legadas e protege confidencialidade/integridade em trânsito. mTLS autentica os dois extremos com certificados de finalidade distinta. AES-GCM fornece cifra autenticada para ficheiros; RSA-PSS/SHA-256 demonstra assinatura de dados com chave independente. Argon2id é uma função de derivação de password deliberadamente custosa e guarda salt/parâmetros no hash. A separação de chaves é essencial: as chaves de CA não são identidades de servidor/cliente, e a chave de assinatura não é a chave TLS.
