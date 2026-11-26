# AI Network Guardian

Monitoramento de conectividade de redes domésticas e pequenas redes privadas **autorizadas**, com
histórico, detecção de quedas e painel web. Processamento 100% local.

**Estado atual: Fases 1 a 8 de 8 implementadas.** Ollama real e testes E2E no navegador precisam ser
executados na sua máquina (veja [Validação](#validação-o-que-foi-e-o-que-não-foi-testado)). Veja [o que existe e o que não existe](#escopo-desta-entrega).

## Escopo desta entrega

| Fase | Conteúdo | Estado |
|---|---|---|
| 1 | Backend FastAPI, banco, migrações, autenticação, frontend base, Docker | ✅ |
| 2 | Coleta de latência/jitter/perda/DNS, persistência, quedas, Dashboard e Network Monitor | ✅ |
| 3 | Descoberta de dispositivos (ARP) e topologia | ✅ |
| 4 | Tempo real (WebSocket) e gráficos de jitter e perda de pacotes | ✅ |
| 5 | Central de alertas e regras | ✅ |
| 6 | Detecção de anomalias (Isolation Forest opcional, com método estatístico de reserva) | ✅ |
| 7 | Agente de IA local (Ollama), somente leitura, com ferramentas controladas | ✅ |
| 8 | Relatórios + CSV, cabeçalhos de segurança, testes E2E (Playwright), documentação | ✅ |

Nenhuma tela ou botão aparece sem funcionar: o agente e a detecção de anomalias mostram seu estado
real (desligado, aprendendo, modelo ausente) em vez de fingir.
**Todos os dados mostrados são medições reais.** Não há dados simulados no projeto.

## O que já funciona

- Medição periódica (padrão: 30 s) por **ICMP**, **TCP connect** e **resolução DNS**.
- Latência mínima/média/máxima, jitter, perda de pacotes e disponibilidade, com histórico.
- Comparação do período atual com o anterior (mesma duração).
- Classificação de incidentes que **diferencia** queda de um destino, falha de DNS, gateway sem
  resposta e queda geral da internet (veja `docs/architecture.md`).
- Login com senha em scrypt + JWT, perfis `admin`/`viewer`, limite de tentativas de login.
- Destinos configuráveis pelo painel, com proteção contra SSRF (loopback, link-local/metadados e
  IPs privados fora das faixas autorizadas são recusados).
- Retenção automática de dados (padrão: 30 dias).
- **Tempo real:** um WebSocket (`/api/v1/ws`) avisa a tela quando há medição, varredura ou alerta
  novo. O token vai na primeira mensagem, não na URL. Se cair, a tela volta ao polling de 15 s e
  mostra "Atualização periódica" no topo; com a conexão ativa mostra "● Ao vivo".
- **Alertas:** novo dispositivo, aparelho conhecido offline (desligado por padrão), queda/falha de
  rede e comportamento fora do padrão. Sem duplicar (um alerta ativo por condição), resolvem
  sozinhos quando a condição passa, podem ser reconhecidos e cada tipo pode ser ligado/desligado.
- **Anomalias:** cada destino é comparado com o *próprio* histórico (janelas de 5 min: latência
  média/máxima, jitter, perda). Usa Isolation Forest se o scikit-learn estiver instalado
  (`pip install -e ".[ml]"`); senão, um método estatístico robusto (mediana/MAD). Só vira
  anomalia se alguma medida se afastar de verdade do normal. Precisa de ~4 h de dados por destino
  e **descreve o desvio, nunca a causa**.
- **AI Guardian:** assistente em linguagem natural via **Ollama local**. Só lê (8 consultas
  fixas), mostra quais consultas fez em cada resposta e recusa qualquer outra ação. Desligado até
  você definir `NG_OLLAMA_MODEL`.
- **Relatórios:** resumo do período (disponibilidade, latência, quedas e tempo fora, dispositivos,
  alertas) e exportação CSV de medições, quedas, dispositivos e alertas.
- **Dispositivos:** varredura da rede local autorizada (conexão TCP à porta 9 de cada IP para
  forçar ARP + leitura da tabela ARP do sistema; sem root, sem Scapy). Inventário por MAC com
  eventos de conexão, desconexão e troca de IP. Dispositivo novo **não é presumido suspeito nem
  confiável**: aparece como "não reconhecido" até um admin marcá-lo como conhecido.
- **Nome automático:** o sistema tenta DNS reverso, mDNS (Apple/Android/impressoras) e NetBIOS
  (Windows/NAS). Celulares com MAC privado muitas vezes não respondem; nesse caso o nome fica em
  branco e você pode escrever o seu. O nome digitado sempre tem prioridade sobre o detectado.
- **Importar do roteador:** cole a tabela de clientes DHCP do painel do roteador e os nomes reais
  são associados pelo MAC (o sistema não acessa o roteador nem pede sua senha).
- **Portas e serviços:** por aparelho, um teste TCP de ~20 portas comuns, sob demanda e só para
  admins, apenas em IPs privados autorizados. Sem coleta de banners e sem tentativa de acesso.
- **Fabricante:** só quando você informa um arquivo OUI (`NG_OUI_FILE`, formato Nmap ou IEEE);
  sem ele aparece "desconhecido". MAC aleatório (privado) é identificado como tal.
- **Topologia:** ligações dispositivo↔gateway são sempre **inferidas** (tracejadas); apenas
  internet↔gateway é **confirmada**, e só quando o monitoramento mostra ambos respondendo.

> **Windows/macOS + Docker:** o Docker Desktop roda numa VM e enxergaria a rede da VM, não a sua
> LAN. Para descobrir dispositivos reais, rode o backend localmente (veja abaixo) e defina
> `NG_SCAN_NETWORK` (ex.: `192.168.100.0/24`). A faixa deve estar em `NG_AUTHORIZED_NETWORKS`.

> **Roteadores que não respondem ping:** se o destino "Gateway local" mostrar 100% de perda mas a
> internet funciona, o roteador provavelmente bloqueia ICMP. Em *Network Monitor → Destinos*,
> adicione o gateway com método **TCP** (porta 53 ou 80).

## Executar com Docker (qualquer sistema)

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
# edite .env: POSTGRES_PASSWORD, NG_SECRET_KEY (32+ chars), NG_ADMIN_PASSWORD (10+ chars)
docker compose up -d --build
```

Abra <http://localhost:8080> e entre com `admin` e a senha definida em `NG_ADMIN_PASSWORD`.
A porta só escuta em `127.0.0.1`; **não exponha o portal na internet**.

Observações por sistema:

- **Linux:** funciona direto.
- **Windows/macOS (Docker Desktop):** o container roda numa VM, então o ping parte da VM, não do seu
  PC. Para medir o gateway da sua LAN real, prefira o modo local abaixo.

## Executar localmente (desenvolvimento)

Pré-requisitos: Python 3.12+, Node 20+.

**Backend** (a partir de `backend/`):

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../.env.example .env            # defina NG_ADMIN_PASSWORD (e, se quiser, NG_GATEWAY_HOST)
alembic upgrade head
uvicorn --factory app.main:create_app --reload --port 8000
```

**Frontend** (a partir de `frontend/`):

```bash
npm install
npm run dev                        # http://localhost:5180 (porta própria e fixa; proxy para :8000)
```

No Windows e no macOS o comando `ping` do sistema é usado automaticamente; no Linux é preciso o
pacote `iputils-ping`.

## Agente de IA (opcional)

```bash
ollama pull llama3.2               # ou outro modelo com suporte a ferramentas
# em backend/.env:
NG_OLLAMA_MODEL=llama3.2           # NG_OLLAMA_URL padrão: http://localhost:11434
```

`NG_OLLAMA_URL` só aceita a própria máquina ou a rede local: os dados da sua rede não vão para a
internet. Modelos pequenos podem errar ou ignorar ferramentas; a resposta sempre mostra as
consultas feitas para você conferir.

## Anomalias com Isolation Forest (opcional)

```bash
pip install -e ".[ml]"             # instala scikit-learn
```

Sem o extra, a detecção funciona com o método estatístico de reserva e a tela informa qual está em uso.

## Qualidade

```bash
./scripts/check.sh                 # Windows: .\scripts\check.ps1
```

Executa `ruff`, `mypy`, `pytest` (backend) e `tsc`, `vitest`, `vite build` (frontend).

Testes E2E no navegador (sobem API com banco descartável e o frontend; agendador desligado):

```bash
cd frontend
npm run e2e:install                # baixa o Chromium (uma vez)
E2E_PYTHON=../backend/.venv/Scripts/python npm run e2e    # Linux/macOS: ../backend/.venv/bin/python
```

## Validação: o que foi e o que não foi testado

- Backend (`pytest`) e frontend (`vitest`) automatizados, com sondas, scanner, WebSocket e modelo de
  linguagem **falsos**: a lógica é verificada, não a sua rede real nem um LLM real.
- Migrações 0001→0005 aplicadas do zero com `alembic check` sem divergência.
- **Não executados no ambiente de desenvolvimento:** specs Playwright (sem navegador disponível),
  Ollama real e a varredura/portas na sua LAN. Rode-os localmente conforme acima.

## Estrutura

```
backend/app/
  api/            rotas e dependências (injeção de dependências do FastAPI)
  core/           config, segurança, exceções, logs, restrição de destinos
  collectors/     sondas ICMP, TCP e DNS; varredura ARP, nomes, portas e base OUI
  services/       regras de negócio (auth, rede, métricas, dispositivos, alertas, anomalias, relatórios)
  ml/             janelas de medição e detectores de anomalia
  agent/          provedor Ollama, ferramentas somente leitura e orquestrador
  websocket/      barramento de eventos em tempo real
  repositories/   acesso a dados
  models/ schemas/ database/ jobs/
  alembic/        migrações
frontend/src/     pages, components, hooks, services, stores, utils, types
docs/             arquitetura, API e modelo de dados
```

## Segurança

- Senhas: scrypt com salt; resposta idêntica para usuário inexistente e senha errada.
- Tokens JWT HS256 com expiração; algoritmo fixado na validação (rejeita `alg: none`).
- Em produção a aplicação **recusa iniciar** sem `NG_SECRET_KEY` forte.
- Destinos só podem ser criados por `admin`; ações sensíveis vão para o log `audit`.
- O comando `ping` é executado sem shell e só com hosts validados.
- O token fica em `sessionStorage` (some ao fechar a aba) e no WebSocket vai na 1ª mensagem.
- Cabeçalhos de segurança em todas as respostas; a API usa CSP restritiva e `no-store`.
- CSV neutraliza fórmulas de planilha (nomes de aparelhos vêm da rede e não são confiáveis).
- Agente: só leitura, lista fechada de ferramentas, argumentos validados, passos limitados e
  resultados tratados como dados (não como instruções). Veja [docs/security.md](docs/security.md).

Limitações conhecidas: o limite de tentativas de login é em memória (uma instância);
HTTPS deve ser terminado por um proxy reverso se o acesso sair de `localhost`.

## Documentação

- [Arquitetura](docs/architecture.md)
- [API](docs/api.md)
- [Modelo de dados](docs/database.md)
- [Segurança](docs/security.md)
