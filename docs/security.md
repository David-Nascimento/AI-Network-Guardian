# Segurança

Princípio: o portal **não deve ser exposto à internet**. Use em `localhost` ou na rede local; se
precisar de acesso remoto, coloque um proxy reverso com HTTPS e autenticação adicional (ou VPN).

## O que o sistema faz

| Área | Medida |
|---|---|
| Senhas | scrypt com salt; resposta idêntica para usuário inexistente e senha errada |
| Sessão | JWT HS256 com expiração, algoritmo fixado (rejeita `alg: none`); token em `sessionStorage` |
| Produção | recusa iniciar sem `NG_SECRET_KEY` forte (32+ caracteres) |
| Login | limite de tentativas por IP (em memória, uma instância) |
| Papéis | `admin` altera; `viewer` só lê. Ações sensíveis vão para o log `audit` |
| Alvos de medição | recusa loopback, link-local/metadados e IPs privados fora de `NG_AUTHORIZED_NETWORKS` |
| Varredura | só redes privadas autorizadas, até 1024 endereços; portas só em IPs privados autorizados, sem banners |
| Comandos | `ping`/`arp` sem shell, só com argumentos validados |
| Cabeçalhos | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`; na API também `Content-Security-Policy: default-src 'none'` e `Cache-Control: no-store` |
| WebSocket | token na 1ª mensagem (fora da URL e dos logs), 5 s para autenticar, fechamento `4401` |
| CSV | células iniciadas por `= + - @` recebem `'` (nomes de aparelhos são dados não confiáveis) |
| Anomalias | sem arquivos de modelo nem `pickle`: o modelo é reaprendido do banco |

## Agente de IA

- **Somente leitura**: nenhuma ferramenta altera estado, executa comandos ou escaneia a rede.
- Lista fechada de 8 ferramentas; nome desconhecido é recusado; argumentos validados (tipo, faixa,
  enumerações, chaves extras rejeitadas); resultado truncado em 6000 caracteres.
- Limite de passos por pergunta; o histórico enviado pelo cliente só aceita `user`/`assistant`
  (não dá para forjar mensagens de sistema ou de ferramenta).
- **Injeção de prompt:** nomes de aparelhos e mensagens vêm da rede e podem conter instruções. O
  prompt do sistema manda tratá-los como dados e, mesmo que o modelo seja enganado, nenhuma
  ferramenta consegue agir.
- `NG_OLLAMA_URL` só aceita a máquina local ou a rede local: dados da rede não saem para a internet.
- Toda pergunta gera um registro `audit` (tamanho da pergunta e ferramentas usadas, não o texto).

## Limitações conhecidas

- Limite de login e barramento de eventos são em memória: com várias instâncias, cada uma tem o seu.
- Sem HTTPS próprio: termine TLS em um proxy reverso se sair de `localhost`.
- Não há limite de taxa específico no `/agent/chat`; o custo fica restrito pelo máximo de passos.
- Modelos de linguagem pequenos erram: a interface sempre mostra as consultas feitas para conferência.
- A descoberta por ARP vê só a sub-rede do computador onde o backend roda.
