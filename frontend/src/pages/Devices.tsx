import { Fragment, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/network/StatCard";
import { useMe } from "@/hooks/useAuth";
import { useDeviceEvents, useDeviceMutations, useDevicePorts, useDevices } from "@/hooks/useDevices";
import { ApiError } from "@/services/api";
import type { Device, DeviceCategory } from "@/types/api";
import { CATEGORY_LABEL } from "@/utils/topology";
import { formatDateTime } from "@/utils/format";

type OnlineFilter = "all" | "online" | "offline";
type KnownFilter = "all" | "known" | "unknown";

const displayName = (d: Device) => d.custom_name ?? d.hostname ?? "Sem nome";
const EVENT_TEXT: Record<string, string> = {
  connected: "Conectou",
  disconnected: "Desconectou",
  ip_changed: "Trocou de IP",
};

function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function NameCell({ device, editable }: { device: Device; editable: boolean }) {
  const { update } = useDeviceMutations();
  const [value, setValue] = useState(device.custom_name ?? "");
  if (!editable) return <span>{displayName(device)}</span>;
  const save = () => {
    if (value.trim() !== (device.custom_name ?? "")) {
      update.mutate({ id: device.id, changes: { custom_name: value.trim() || null } });
    }
  };
  return (
    <Input
      aria-label={`Nome de ${device.ip}`}
      className="h-8 min-w-40"
      placeholder={device.hostname ?? "Dar um nome"}
      value={value}
      maxLength={80}
      onChange={(e) => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
    />
  );
}

function History({ deviceId }: { deviceId: number }) {
  const events = useDeviceEvents(deviceId);
  if (events.isLoading) return <Skeleton className="h-10 w-full" />;
  if (events.isError) return <ErrorState error={events.error} onRetry={() => void events.refetch()} />;
  const list = events.data ?? [];
  if (list.length === 0) return <p className="text-xs text-muted-foreground">Sem eventos registrados.</p>;
  return (
    <ul className="space-y-1 text-xs">
      {list.map((e) => (
        <li key={e.id}>
          <span className="text-muted-foreground">{formatDateTime(e.ts)}</span> ·{" "}
          <span className="font-medium">{EVENT_TEXT[e.event_type] ?? e.event_type}</span>
          {e.detail ? ` — ${e.detail}` : ""}
        </li>
      ))}
    </ul>
  );
}

function Ports({ device, editable }: { device: Device; editable: boolean }) {
  const ports = useDevicePorts(device.id);
  const { scanPorts } = useDeviceMutations();
  const scanning = scanPorts.isPending && scanPorts.variables === device.id;
  return (
    <div className="space-y-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Portas e serviços</span>
        {editable && (
          <Button size="sm" variant="outline" disabled={scanning || !device.online}
            onClick={() => scanPorts.mutate(device.id)}>
            {scanning ? "Escaneando…" : "Escanear portas"}
          </Button>
        )}
      </div>
      {scanPorts.error && <p role="alert" className="text-danger">{errorText(scanPorts.error, "Falha ao escanear.")}</p>}
      {ports.isLoading ? <Skeleton className="h-8 w-full" /> : ports.isError ? (
        <ErrorState error={ports.error} onRetry={() => void ports.refetch()} />
      ) : (ports.data ?? []).length > 0 ? (
        <ul className="space-y-1">
          {(ports.data ?? []).map((p) => (
            <li key={p.port}><span className="font-mono">{p.port}</span> — {p.service}</li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">
          {device.ports_scanned_at
            ? `Nenhuma das portas comuns respondeu em ${formatDateTime(device.ports_scanned_at)}.`
            : "Ainda não escaneado."}
        </p>
      )}
      <p className="text-muted-foreground">
        Testa só ~20 portas TCP comuns, sem tentar acessar o serviço. Porta aberta não é falha de
        segurança: indica o que o aparelho oferece. O rótulo é o uso convencional da porta.
      </p>
    </div>
  );
}

function ImportNames({ onDone }: { onDone: () => void }) {
  const { importNames } = useDeviceMutations();
  const [text, setText] = useState("");
  return (
    <Card>
      <CardHeader><CardTitle>Importar nomes do roteador</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Abra a página do roteador que lista os aparelhos conectados (DHCP / clientes), copie a
          tabela e cole abaixo. Os nomes são associados pelo MAC. O nome que você digitou em
          "Nome" continua tendo prioridade.
        </p>
        <textarea aria-label="Tabela do roteador" rows={6} value={text} maxLength={200000}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-md border border-border bg-background p-2 font-mono text-xs" />
        {importNames.data && (
          <p role="status">
            {importNames.data.parsed} linhas lidas, {importNames.data.matched} aparelhos
            encontrados, {importNames.data.updated} nomes atualizados.
          </p>
        )}
        {importNames.error && <p role="alert" className="text-danger">{errorText(importNames.error, "Falha ao importar.")}</p>}
        <div className="flex gap-2">
          <Button disabled={!text.trim() || importNames.isPending} onClick={() => importNames.mutate(text)}>
            {importNames.isPending ? "Importando…" : "Importar"}
          </Button>
          <Button variant="ghost" onClick={onDone}>Fechar</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function Devices() {
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";
  const devices = useDevices();
  const { update, scan, markAllKnown } = useDeviceMutations();
  const [online, setOnline] = useState<OnlineFilter>("all");
  const [known, setKnown] = useState<KnownFilter>("all");
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [importing, setImporting] = useState(false);

  const all = devices.data ?? [];
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return all.filter(
      (d) =>
        (online === "all" || (online === "online") === d.online) &&
        (known === "all" || (known === "known") === d.is_known) &&
        (!q || [d.ip, d.mac, d.hostname, d.vendor, d.custom_name].some((v) => v?.toLowerCase().includes(q))),
    );
  }, [all, online, known, search]);

  if (devices.isError) return <ErrorState error={devices.error} onRetry={() => void devices.refetch()} />;
  const unknownCount = all.filter((d) => !d.is_known).length;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Dispositivos</h1>
          <p className="text-sm text-muted-foreground">
            Descobertos na rede local autorizada via ARP · atualização automática
          </p>
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setImporting((v) => !v)}>
              Importar nomes do roteador
            </Button>
            <Button variant="outline" disabled={markAllKnown.isPending || unknownCount === 0}
              onClick={() => { if (window.confirm(`Marcar ${unknownCount} dispositivo(s) como conhecidos?`)) markAllKnown.mutate(); }}>
              Marcar todos como conhecidos
            </Button>
            <Button disabled={scan.isPending} onClick={() => scan.mutate()}>
              {scan.isPending ? "Varrendo…" : "Varrer agora"}
            </Button>
          </div>
        )}
      </div>

      {isAdmin && importing && <ImportNames onDone={() => setImporting(false)} />}

      {scan.data && (
        <p role="status" className="text-sm text-muted-foreground">
          Varredura de {scan.data.network}: {scan.data.found} encontrados, {scan.data.new} novos,{" "}
          {scan.data.reconnected} reconectados, {scan.data.disconnected} desconectados.
        </p>
      )}
      {scan.error && <p role="alert" className="text-sm text-danger">{errorText(scan.error, "A varredura falhou.")}</p>}
      {update.error && <p role="alert" className="text-sm text-danger">{errorText(update.error, "Não foi possível salvar.")}</p>}

      <section aria-label="Resumo" className="grid gap-4 sm:grid-cols-3">
        <StatCard title="Online" value={all.filter((d) => d.online).length} loading={devices.isLoading} className="text-success" />
        <StatCard title="Total conhecido pelo sistema" value={all.length} loading={devices.isLoading} className="text-network" />
        <StatCard title="Não reconhecidos" value={unknownCount} loading={devices.isLoading}
          className={unknownCount > 0 ? "text-warning" : "text-success"}
          hint="Não reconhecido não significa malicioso: confirme se o aparelho é seu." />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Inventário</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Input aria-label="Buscar" placeholder="Buscar IP, MAC, nome…" className="h-8 w-48" value={search}
              onChange={(e) => setSearch(e.target.value)} />
            <Select aria-label="Filtrar por status" className="h-8 w-32" value={online}
              onChange={(e) => setOnline(e.target.value as OnlineFilter)}>
              <option value="all">Todos</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
            </Select>
            <Select aria-label="Filtrar por reconhecimento" className="h-8 w-40" value={known}
              onChange={(e) => setKnown(e.target.value as KnownFilter)}>
              <option value="all">Todos</option>
              <option value="known">Conhecidos</option>
              <option value="unknown">Não reconhecidos</option>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {devices.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : rows.length === 0 ? (
            <EmptyState
              title={all.length === 0 ? "Nenhum dispositivo descoberto" : "Nenhum dispositivo com esses filtros"}
              hint={all.length === 0 ? "A primeira varredura roda automaticamente; administradores podem usar “Varrer agora”." : undefined}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Dispositivos da rede</caption>
                <thead className="text-xs text-muted-foreground">
                  <tr>
                    {["Nome", "IP", "MAC", "Fabricante", "Categoria", "Status", "Última detecção", "Conhecido"].map((h) => (
                      <th key={h} scope="col" className="py-2 pr-3 font-medium">{h}</th>
                    ))}
                    <th scope="col" className="py-2 font-medium"><span className="sr-only">Histórico</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((d) => (
                    <Fragment key={d.id}>
                      <tr>
                        <td className="py-2 pr-3"><NameCell device={d} editable={isAdmin} /></td>
                        <td className="py-2 pr-3 tabular-nums">{d.ip}</td>
                        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">{d.mac}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{d.vendor ?? "desconhecido"}</td>
                        <td className="py-2 pr-3">
                          {isAdmin ? (
                            <Select aria-label={`Categoria de ${d.ip}`} className="h-8 w-36" value={d.category}
                              onChange={(e) => update.mutate({ id: d.id, changes: { category: e.target.value as DeviceCategory } })}>
                              {Object.entries(CATEGORY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                            </Select>
                          ) : (CATEGORY_LABEL[d.category])}
                        </td>
                        <td className="py-2 pr-3"><Badge tone={d.online ? "success" : "neutral"}>{d.online ? "Online" : "Offline"}</Badge></td>
                        <td className="py-2 pr-3 text-muted-foreground">{formatDateTime(d.last_seen)}</td>
                        <td className="py-2 pr-3">
                          {isAdmin ? (
                            <input type="checkbox" aria-label={`Conhecido: ${d.ip}`} checked={d.is_known}
                              onChange={(e) => update.mutate({ id: d.id, changes: { is_known: e.target.checked } })} />
                          ) : (
                            <Badge tone={d.is_known ? "success" : "warning"}>{d.is_known ? "Sim" : "Não"}</Badge>
                          )}
                        </td>
                        <td className="py-2">
                          <Button variant="ghost" size="sm" aria-expanded={openId === d.id}
                            onClick={() => setOpenId(openId === d.id ? null : d.id)}>
                            Histórico
                          </Button>
                        </td>
                      </tr>
                      {openId === d.id && (
                        <tr>
                          <td colSpan={9} className="grid gap-4 bg-muted/40 px-3 py-3 md:grid-cols-2">
                            <History deviceId={d.id} />
                            <Ports device={d} editable={isAdmin} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
