# Arquitetura (Fases 1 a 8)

## Camadas

```
HTTP ─► api/routes ─► services ─► repositories ─► SQLAlchemy ─► PostgreSQL | SQLite
                          ▲
 APScheduler ─► jobs/tasks ┘      collectors (ICMP · TCP · DNS) ─► ProbeResult
```

- **api/**: valida entrada (Pydantic), resolve dependências (`dependencies.py`) e chama serviços.
  Nenhuma regra de negócio nas rotas.
- **services/**: `AuthService`, `NetworkService`, `MetricsService` e `connectivity.py` (regras puras).
- **repositories/**: únicas classes que montam consultas SQL.
- **collectors/**: só medem. Não conhecem banco; devolvem `ProbeResult`.
- **jobs/**: orquestram um ciclo (medir em paralelo → gravar → avaliar incidentes) e a retenção.
- **core/**: configuração (`NG_*`), segurança, exceções com handler central, logs JSON, `network_guard`.

`create_app(settings, engine=..., probes=...)` é uma fábrica: testes injetam banco em memória e sondas
falsas, sem rede real.

## Ciclo de coleta

1. Lê os destinos ativos e os copia para objetos imutáveis (`TargetSpec`).
2. Mede todos em paralelo (até 8 threads). Se a sonda não puder operar (ex.: sem `ping`), o destino é
   **ignorado no ciclo** — indisponibilidade do coletor nunca vira "queda de rede".
3. Grava uma `NetworkMetric` por destino e chama `NetworkService.evaluate()`.

## Classificação de incidentes (`services/connectivity.py`)

Um destino é considerado **fora** após `NG_FAILURE_THRESHOLD` medições seguidas sem nenhuma resposta
(histerese: evita alarme por um pacote perdido). A partir daí:

| Situação | Incidente | Severidade |
|---|---|---|
| Todos os gateways fora | `gateway_down` (suprime os demais: são consequência) | crítica |
| 2+ destinos externos, todos fora | `internet_down` | crítica |
| Um externo fora, outros respondem | `target_down` (só aquele destino) | atenção |
| DNS fora | `dns_down`; só afirma "internet ativa" se há medições dos externos | atenção |

Com **um único** destino externo não se afirma queda geral. Incidentes têm chave estável, então a
repetição da falha não duplica eventos; ao voltar a responder, o evento recebe `ended_at`.

## Descoberta e topologia (Fase 3)

- `collectors/arp_collector.py` varre a rede (TCP à porta 9 para forçar ARP), lê a tabela de
  vizinhos do SO (`ip neigh`, `/proc/net/arp`, `arp -a`) e devolve `DiscoveredHost`. O coletor
  só mede; não decide nada.
- `services/device_service.py` reconcilia a varredura com o inventário (novo, reconectado, troca
  de IP, offline após N varreduras). Se o coletor não pode rodar, nada é alterado.
- `services/topology_service.py` monta o grafo. Nenhum dispositivo é assumido como gateway;
  sem gateway configurado aparece "Gateway (não configurado)".
- A rede varrida precisa ser privada, estar em `NG_AUTHORIZED_NETWORKS` e ter até 1024 endereços.

## Tempo real e alertas (Fases 4 e 5)

- `websocket/bus.py`: `EventBus` thread-safe. Os jobs (threads do APScheduler) publicam **depois do
  commit**, via `loop.call_soon_threadsafe`; cada cliente tem fila limitada que descarta quando enche.
- `services/alert_service.py`: cria sem repetir (`dedupe_key`), resolve quando a condição some,
  reconhece, liga/desliga tipos. Eventos ficam em `pending` até o commit do job.
- Só os **jobs** publicam eventos; mudanças feitas por rota dependem da invalidação do cliente.

## Anomalias (Fase 6)

`ml/features.py` agrega medições em janelas (padrão 5 min); janelas sem nenhuma resposta ficam de
fora (quedas já são incidentes). `ml/detector.py` aprende a linha de base **por destino**
(mediana/MAD com piso de escala) e julga as últimas janelas fechadas:

| Método | Quando | Observação |
|---|---|---|
| `isolation_forest` | scikit-learn instalado e ≥ 20 janelas | só marca se também houver desvio robusto (|z| ≥ 3,5) |
| `robust_zscore` | caso contrário | Python puro |

Mínimo de `NG_ML_MIN_WINDOWS` (48) janelas por destino. O alerta traz os desvios em texto e diz que
não indica a causa.

## Agente de IA (Fase 7)

`agent/orchestrator.py` roda o laço modelo → ferramenta → modelo, com no máximo `NG_AGENT_MAX_STEPS`
passos. `agent/tools.py` tem 8 ferramentas somente leitura em lista fechada, com argumentos
validados e resultado truncado. O provedor (`agent/provider.py`) é um `Protocol`; testes usam um
modelo roteirizado. A resposta devolve o rastro das consultas feitas.

## Relatórios (Fase 8)

`services/report_service.py` agrega dados já medidos (nada estimado) e gera CSV com neutralização de
fórmulas. `core/middleware.py` aplica os cabeçalhos de segurança.

## Segurança

- `network_guard.validate_host`: recusa loopback, link-local (inclui `169.254.169.254`), multicast,
  não-especificado e reservados; IP privado só dentro de `NG_AUTHORIZED_NETWORKS`; hostnames precisam
  ter sintaxe válida (impede injeção de opções no `ping`).
- Autenticação por Bearer JWT; `admin` altera destinos, `viewer` só lê.
- Rate limit de login por IP (janela deslizante, em memória).

## Decisões

- **Sem Scapy/root nesta fase**: ICMP via comando `ping` do SO, que funciona sem privilégios. Scapy
  entra na Fase 3 (ARP).
- **SQLAlchemy síncrono**: as rotas são `def` (threadpool do FastAPI); simples e suficiente para o
  volume de uma rede doméstica.
- **Datas**: sempre UTC com fuso (`UTCDateTime`), inclusive no SQLite.
- **Migrações independentes do código**: o `env.py` renderiza `UTCDateTime` como `DateTime(timezone=True)`.
- **Tempo real:** WebSocket só como *aviso*; a verdade continua na API REST e o polling segue como rede de segurança.

## Critérios de aceite

**Fase 1**
- [x] `alembic upgrade head` cria o esquema e `alembic check` não acusa divergência.
- [x] `/health` e `/health/ready` (503 com banco indisponível).
- [x] Login, rotas protegidas, papéis, rate limit, erros em formato único.
- [x] Frontend compila (`tsc`, `vite build`), com login, tema claro/escuro e menu recolhível.

**Fase 2**
- [x] Coleta periódica persistida; consulta de histórico, resumo e comparação de períodos.
- [x] Queda de um destino distinta de queda geral e de falha do gateway.
- [x] Coletor indisponível não gera incidentes; timeout tratado como falha de medição.
- [x] Destinos recusados por regras anti-SSRF; retenção de dados testada.
