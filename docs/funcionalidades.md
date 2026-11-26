# Funcionalidades

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

## Estrutura do código

```
backend/app/
  api/            rotas e dependências
  core/           config, segurança, exceções, logs, middleware
  collectors/     sondas ICMP/TCP/DNS, ARP, nomes, portas e base OUI
  services/       regras de negócio
  ml/ agent/ websocket/   anomalias, agente de IA e eventos em tempo real
  repositories/ models/ schemas/ database/ jobs/
backend/alembic/  migrações
frontend/src/     pages, components, hooks, services, stores, utils, types
```
