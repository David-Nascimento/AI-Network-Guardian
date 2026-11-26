# API

Documentação interativa (OpenAPI): `http://localhost:8000/docs` (modo local).
Prefixo: `/api/v1`. Autenticação: `Authorization: Bearer <token>` (exceto login e health).

Erros seguem sempre `{"error": {"code": "...", "message": "...", "details"?: [...]}}`.

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| GET | `/health` | público | liveness |
| GET | `/health/ready` | público | banco + scheduler; 503 se algo falhar |
| POST | `/auth/login` | público | `{username, password}` → `{access_token, expires_in}`; 429 após excesso |
| GET | `/auth/me` | qualquer | usuário atual |
| GET | `/network/status` | qualquer | estado (`online/degraded/offline/unknown`), resumo, destinos, incidentes ativos |
| GET | `/network/targets` | qualquer | lista destinos |
| POST | `/network/targets` | admin | cria destino (valida host, método e porta) |
| PATCH | `/network/targets/{id}` | admin | renomeia / ativa / pausa |
| DELETE | `/network/targets/{id}` | admin | remove destino e histórico |
| GET | `/network/events` | qualquer | `hours`, `active_only`, `limit` |
| GET | `/metrics/history` | qualquer | `hours`, `target_id`, `bucket_minutes` (agrega por janela) |
| GET | `/metrics/summary` | qualquer | min/méd/máx de latência, jitter, perda, disponibilidade |
| GET | `/metrics/compare` | qualquer | período atual × anterior, com deltas |
| GET | `/devices` | qualquer | inventário; filtros `online`, `known` |
| POST | `/devices/scan` | admin | varredura imediata; 503 se o coletor não puder rodar (inventário intacto); 422 se a rede for inválida |
| POST | `/devices/mark-all-known` | admin | marca todos como conhecidos → `{updated}` |
| GET | `/devices/{id}` | qualquer | um dispositivo |
| PATCH | `/devices/{id}` | admin | `custom_name` (nulo limpa), `category`, `is_known` |
| GET | `/devices/{id}/events` | qualquer | `connected`, `disconnected`, `ip_changed` |
| POST | `/devices/import-names` | admin | `{text}` com a tabela DHCP copiada do roteador; associa nomes pelo MAC → `{parsed, matched, updated}` |
| GET | `/devices/{id}/ports` | qualquer | portas abertas da última varredura de portas |
| POST | `/devices/{id}/ports/scan` | admin | testa ~20 portas TCP comuns; recusa IP fora das faixas privadas autorizadas (422) |
| GET | `/topology` | qualquer | nós, arestas (`confirmed`/`inferred`) e notas |
| GET | `/alerts` | qualquer | `status` (`active`/`new`/`acknowledged`/`resolved`/`all`), `severity`, `limit` |
| GET | `/alerts/summary` | qualquer | `{new, acknowledged, critical_active}` (selo do menu) |
| GET | `/alerts/rules` | qualquer | tipos de alerta e se estão ligados |
| PATCH | `/alerts/rules/{kind}` | admin | `{enabled}`; tipo desconhecido → 404 |
| POST | `/alerts/{id}/ack` | admin | reconhece um alerta |
| POST | `/alerts/ack-all` | admin | reconhece todos os novos → `{updated}` |
| GET | `/ml/status` | qualquer | método em uso, scikit-learn disponível, janelas por destino e se está pronto |
| GET | `/ml/anomalies` | qualquer | `hours`, `target_id`, `limit`: janelas fora do padrão, com descrição dos desvios |
| GET | `/agent/status` | qualquer | `enabled`, `model`, `reachable`, `model_installed`, `tools` |
| POST | `/agent/chat` | qualquer | `{message, history[]}` → `{answer, stopped, steps, tool_calls[]}`; 503 se desligado/inacessível |
| GET | `/reports/summary` | qualquer | `hours` (1–720): disponibilidade, latência, quedas, dispositivos, alertas |
| GET | `/reports/export` | qualquer | `kind` = `metrics`/`events`/`devices`/`alerts`, `hours` → CSV (UTF-8 com BOM) |
| WS | `/ws` | qualquer | tempo real (abaixo) |

### WebSocket `/api/v1/ws`

1. Conecte e envie **em até 5 s** `{"type":"auth","token":"<jwt>"}`. Token inválido/ausente: o
   servidor fecha com código `4401`.
2. O servidor responde `{"type":"ready"}` e depois envia `{"type","data","ts"}` por evento:
   `network.updated`, `devices.updated`, `device.event`, `alert.created`, `alert.updated`,
   `anomalies.updated`.
3. Eventos são só um aviso para a tela buscar de novo; os dados continuam vindo da API REST.
   Clientes lentos perdem eventos (fila limitada), nunca travam o servidor.

Corpo de `POST /network/targets`:

```json
{ "name": "Roteador", "host": "192.168.100.1", "kind": "gateway", "method": "tcp", "port": 53 }
```

Regras: `method=tcp` exige `port`; `kind=dns` ⇔ `method=dns`; hosts proibidos retornam 422.
