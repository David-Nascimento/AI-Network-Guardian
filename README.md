# AI Network Guardian

Monitoramento de redes domésticas e pequenas redes privadas **autorizadas**: latência, quedas,
dispositivos, alertas, anomalias e um assistente de IA local. Tudo roda na sua máquina e
**todos os dados mostrados são medições reais**, sem dados simulados.

## O que tem

- **Network Monitor:** latência, jitter, perda e disponibilidade (ICMP, TCP e DNS), com quedas
  classificadas (destino, DNS, gateway ou internet).
- **Dispositivos e topologia:** descoberta por ARP, nomes automáticos, fabricante e portas.
  Aparelho novo aparece como "não reconhecido", nunca como suspeito.
- **Alertas** e **anomalias** (cada destino comparado com o próprio histórico), com atualização
  em tempo real por WebSocket.
- **AI Guardian:** assistente via Ollama local, somente leitura (opcional).
- **Relatórios** do período e exportação em CSV.

Detalhes de cada recurso: [docs/funcionalidades.md](docs/funcionalidades.md).

## Executar (desenvolvimento)

Requisitos: Python 3.12+ e Node 20+.

**Terminal 1 — backend**

```powershell
# Windows (PowerShell)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item ..\.env.example .env     # edite o .env: defina NG_ADMIN_PASSWORD (10+ caracteres)
alembic upgrade head
uvicorn --factory app.main:create_app --reload --port 8000
```

```bash
# Linux/macOS
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env            # defina NG_ADMIN_PASSWORD (10+ caracteres)
alembic upgrade head
uvicorn --factory app.main:create_app --reload --port 8000
```

**Terminal 2 — frontend** (a partir da raiz do projeto)

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5180
```

Nas próximas vezes, basta ativar o venv (`.\.venv\Scripts\Activate.ps1`) e rodar o `uvicorn`,
e rodar `npm run dev` no frontend. Se o PowerShell bloquear o script de ativação, use
`.\.venv\Scripts\python.exe -m uvicorn --factory app.main:create_app --reload --port 8000`.

Entre com `admin` e a senha de `NG_ADMIN_PASSWORD`. Para descobrir dispositivos da sua LAN, rode
o backend localmente (não em Docker no Windows/macOS) e, se preciso, defina `NG_SCAN_NETWORK`
(ex.: `192.168.100.0/24`).

**Docker:** `cp .env.example .env`, preencha as senhas e rode `docker compose up -d --build`
(<http://localhost:8080>). No Windows/macOS ele enxerga a rede da VM do Docker, não a sua LAN.

### Opcionais

- **Agente de IA:** `ollama pull llama3.2` e `NG_OLLAMA_MODEL=llama3.2` no `.env`.
- **Isolation Forest:** `pip install -e ".[ml]"` (sem isso, usa um método estatístico de reserva).

## Qualidade

```bash
./scripts/check.sh                 # Windows: .\scripts\check.ps1
```

Roda ruff, mypy, pytest, tsc, vitest e o build. Testes E2E: `cd frontend && npm run e2e:install && npm run e2e`.

Os testes usam sondas, scanner e modelo de linguagem **falsos**: validam a lógica, não a sua rede
real. Os specs Playwright e o Ollama real precisam ser executados na sua máquina.

## Segurança

Não exponha o portal à internet. Senhas em scrypt, JWT com expiração, perfis `admin`/`viewer`,
proteção contra SSRF, cabeçalhos de segurança e agente somente leitura.
Veja [docs/security.md](docs/security.md).

## Documentação

[Funcionalidades](docs/funcionalidades.md) · [Arquitetura](docs/architecture.md) ·
[API](docs/api.md) · [Modelo de dados](docs/database.md) · [Segurança](docs/security.md)
