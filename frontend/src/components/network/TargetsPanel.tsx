import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, Field } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { useTargetMutations, useTargets } from "@/hooks/useNetwork";
import { ApiError } from "@/services/api";
import type { TargetKind, TargetMethod } from "@/types/api";

const KIND_LABEL: Record<TargetKind, string> = { gateway: "Gateway", external: "Externo", dns: "DNS" };

export function TargetsPanel({ isAdmin }: { isAdmin: boolean }) {
  const targets = useTargets();
  const { create, toggle, remove } = useTargetMutations();
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [kind, setKind] = useState<TargetKind>("external");
  const [method, setMethod] = useState<TargetMethod>("icmp");
  const [port, setPort] = useState("");

  // kind "dns" exige method "dns" (e vice-versa); tcp exige porta.
  const changeKind = (k: TargetKind) => {
    setKind(k);
    setMethod(k === "dns" ? "dns" : method === "dns" ? "icmp" : method);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        name: name.trim(),
        host: host.trim(),
        kind,
        method,
        port: method === "tcp" ? Number(port) : null,
        enabled: true,
      },
      { onSuccess: () => { setName(""); setHost(""); setPort(""); } },
    );
  };

  if (targets.isError) return <ErrorState error={targets.error} onRetry={() => void targets.refetch()} />;
  if (targets.isLoading) return <Skeleton className="h-32 w-full" />;
  const list = targets.data ?? [];

  return (
    <div className="space-y-4">
      {list.length === 0 ? (
        <EmptyState title="Nenhum destino configurado" hint="Adicione ao menos dois destinos externos para distinguir falha pontual de queda geral." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Destinos monitorados</caption>
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">Nome</th>
                <th scope="col" className="py-2 pr-3 font-medium">Destino</th>
                <th scope="col" className="py-2 pr-3 font-medium">Tipo</th>
                <th scope="col" className="py-2 pr-3 font-medium">Estado</th>
                {isAdmin && <th scope="col" className="py-2 font-medium"><span className="sr-only">Ações</span></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.map((t) => (
                <tr key={t.id}>
                  <td className="py-2 pr-3 font-medium">{t.name}</td>
                  <td className="py-2 pr-3 tabular-nums text-muted-foreground">
                    {t.host}{t.port ? `:${t.port}` : ""} · {t.method.toUpperCase()}
                  </td>
                  <td className="py-2 pr-3"><Badge tone="network">{KIND_LABEL[t.kind]}</Badge></td>
                  <td className="py-2 pr-3">
                    <Badge tone={t.enabled ? "success" : "neutral"}>{t.enabled ? "Ativo" : "Pausado"}</Badge>
                  </td>
                  {isAdmin && (
                    <td className="flex justify-end gap-1 py-2">
                      <Button variant="outline" size="sm" disabled={toggle.isPending}
                        onClick={() => toggle.mutate({ id: t.id, enabled: !t.enabled })}>
                        {t.enabled ? "Pausar" : "Ativar"}
                      </Button>
                      <Button variant="ghost" size="icon" aria-label={`Remover ${t.name}`} disabled={remove.isPending}
                        onClick={() => { if (window.confirm(`Remover "${t.name}" e seu histórico?`)) remove.mutate(t.id); }}>
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isAdmin && (
        <form onSubmit={submit} className="grid gap-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-6">
          <Field label="Nome" htmlFor="t-name">
            <Input id="t-name" required value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Host ou IP" htmlFor="t-host">
            <Input id="t-host" required value={host} onChange={(e) => setHost(e.target.value)} />
          </Field>
          <Field label="Tipo" htmlFor="t-kind">
            <Select id="t-kind" value={kind} onChange={(e) => changeKind(e.target.value as TargetKind)}>
              <option value="external">Externo</option>
              <option value="gateway">Gateway</option>
              <option value="dns">DNS</option>
            </Select>
          </Field>
          <Field label="Método" htmlFor="t-method">
            <Select id="t-method" value={method} disabled={kind === "dns"}
              onChange={(e) => setMethod(e.target.value as TargetMethod)}>
              {kind === "dns" ? <option value="dns">DNS</option> : (
                <>
                  <option value="icmp">ICMP (ping)</option>
                  <option value="tcp">TCP</option>
                </>
              )}
            </Select>
          </Field>
          <Field label="Porta (TCP)" htmlFor="t-port">
            <Input id="t-port" type="number" min={1} max={65535} disabled={method !== "tcp"} required={method === "tcp"}
              value={port} onChange={(e) => setPort(e.target.value)} />
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={create.isPending} className="w-full">
              <Plus className="h-4 w-4" aria-hidden /> Adicionar
            </Button>
          </div>
          {create.error && (
            <p role="alert" className="text-sm text-danger sm:col-span-2 lg:col-span-6">
              {create.error instanceof ApiError ? create.error.message : "Não foi possível adicionar o destino."}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
