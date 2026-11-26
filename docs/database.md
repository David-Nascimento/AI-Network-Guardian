# Modelo de dados (Fases 1 a 6)

Migração: `backend/alembic/versions/0001_schema_inicial.py`. PostgreSQL em produção, SQLite opcional.

| Tabela | Finalidade | Campos principais |
|---|---|---|
| `users` | usuários do portal | `username` (único), `password_hash` (scrypt), `role`, `is_active` |
| `monitor_targets` | destinos monitorados | `name` (único), `host`, `kind` (gateway/external/dns), `method` (icmp/tcp/dns), `port`, `enabled` |
| `network_metrics` | uma linha por destino a cada ciclo | `target_id`, `ts` (UTC), `success`, `sent`, `received`, `latency_min/avg/max_ms`, `jitter_ms`, `packet_loss_pct`, `error`; índice `(target_id, ts)` |
| `network_events` | quedas e incidentes | `incident_key`, `event_type`, `severity`, `target_id`, `message`, `details` (JSON, evidências), `started_at`, `ended_at` (nulo = em andamento) |

| `devices` | inventário descoberto | `mac` (único, minúsculo com `:`), `ip`, `hostname`, `vendor`, `custom_name`, `category`, `is_known` (padrão falso), `online`, `missed_scans`, `first_seen`, `last_seen` |
| `device_events` | histórico do dispositivo | `device_id` (cascata), `event_type` (connected/disconnected/ip_changed), `detail`, `ts` |

| `device_ports` | portas TCP abertas por dispositivo | `device_id` (cascata), `port`, `first_seen`, `last_seen`; único `(device_id, port)`; `devices.ports_scanned_at` guarda quando foi a última varredura |

Migrações: `0002_dispositivos.py` e `0003_portas_dispositivos.py`. Um dispositivo só fica offline após
`NG_OFFLINE_AFTER_SCANS` varreduras seguidas sem resposta.

| `alerts` | central de alertas | `kind`, `severity`, `title`, `message`, `dedupe_key`, `device_id` (`SET NULL`), `created_at`, `resolved_at`, `acknowledged_at/by`; índice `(dedupe_key, resolved_at)` |
| `alert_rules` | liga/desliga por tipo | `kind` (PK), `enabled` |
| `anomalies` | janelas fora do padrão | `target_id` (cascata), `window_start`, `method`, `score`, `features` (JSON), `deviations` (JSON); único `(target_id, window_start)` |

Migrações `0004_alertas.py` e `0005_anomalias.py`. Um alerta *ativo* por `dedupe_key`; ele é
resolvido (não apagado) quando a condição passa. O modelo de anomalias não é persistido: é
reaprendido a cada execução a partir de `network_metrics` (sem arquivos de modelo, sem `pickle`).

`network_metrics` e `network_events` referenciam `monitor_targets` com remoção em cascata / `SET NULL`.
Relatórios são calculados na hora a partir destas tabelas; nada extra é gravado.
