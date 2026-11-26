import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { api, ApiError } from "@/services/api";
import type { ChatTurn, ToolTrace } from "@/types/api";

interface Entry extends ChatTurn {
  tools?: ToolTrace[];
  stopped?: "answered" | "max_steps";
}

const SUGGESTIONS = [
  "Como está minha internet nas últimas 24 horas?",
  "Quais dispositivos estão online agora?",
  "Há algum alerta que eu precise ver?",
  "Houve alguma queda recente?",
];

function StatusCard() {
  const status = useQuery({ queryKey: ["agent", "status"], queryFn: api.agentStatus, refetchInterval: 30_000 });
  if (status.isLoading) return <Skeleton className="h-16 w-full" />;
  if (status.isError) return <ErrorState error={status.error} onRetry={() => void status.refetch()} />;
  const s = status.data;
  if (!s) return null;
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-3 pt-4 text-sm">
        {!s.enabled ? (
          <>
            <Badge tone="neutral">Agente desligado</Badge>
            <span className="text-muted-foreground">{s.detail}</span>
          </>
        ) : !s.reachable ? (
          <>
            <Badge tone="danger">Ollama inacessível</Badge>
            <span className="text-muted-foreground">{s.detail}</span>
          </>
        ) : !s.model_installed ? (
          <>
            <Badge tone="warning">Modelo ausente</Badge>
            <span className="text-muted-foreground">
              {s.detail}. Instale com <code>ollama pull {s.model}</code>.
            </span>
          </>
        ) : (
          <>
            <Badge tone="success">Pronto</Badge>
            <span className="text-muted-foreground">Modelo local: {s.model} · somente leitura · {s.tools.length} consultas disponíveis</span>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function Guardian() {
  const status = useQuery({ queryKey: ["agent", "status"], queryFn: api.agentStatus });
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const ready = Boolean(status.data?.enabled && status.data.reachable && status.data.model_installed);

  const chat = useMutation({
    mutationFn: (v: { message: string; history: ChatTurn[] }) => api.agentChat(v.message, v.history),
    onSuccess: (res) =>
      setEntries((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, tools: res.tool_calls, stopped: res.stopped },
      ]),
  });

  const send = (message: string) => {
    const clean = message.trim();
    if (!clean || chat.isPending) return;
    const history = entries.map(({ role, content }) => ({ role, content }));
    setEntries((prev) => [...prev, { role: "user", content: clean }]);
    setText("");
    chat.mutate({ message: clean, history });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(text);
  };

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">AI Guardian</h1>
        <p className="text-sm text-muted-foreground">
          Pergunte sobre a sua rede. O assistente roda no seu computador (Ollama), só lê os dados do sistema e
          mostra quais consultas fez em cada resposta.
        </p>
      </div>

      <StatusCard />

      <Card>
        <CardHeader>
          <CardTitle>Conversa</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {entries.length === 0 && (
            <div className="flex flex-wrap gap-2" aria-label="Sugestões">
              {SUGGESTIONS.map((q) => (
                <Button key={q} size="sm" variant="outline" disabled={!ready || chat.isPending} onClick={() => send(q)}>
                  {q}
                </Button>
              ))}
            </div>
          )}

          <ol className="space-y-3" aria-live="polite" aria-label="Mensagens">
            {entries.map((e, i) => (
              <li key={i} className={e.role === "user" ? "text-right" : ""}>
                <div
                  className={
                    e.role === "user"
                      ? "inline-block max-w-[85%] rounded-lg bg-primary px-3 py-2 text-left text-sm text-primary-foreground"
                      : "inline-block max-w-[85%] whitespace-pre-wrap rounded-lg bg-muted px-3 py-2 text-left text-sm"
                  }
                >
                  {e.content}
                </div>
                {e.tools && e.tools.length > 0 && (
                  <details className="mt-1 text-xs text-muted-foreground">
                    <summary className="cursor-pointer">Consultas feitas ({e.tools.length})</summary>
                    <ul className="mt-1 space-y-0.5">
                      {e.tools.map((t, k) => (
                        <li key={k}>
                          <code>{t.name}</code>
                          {Object.keys(t.arguments).length > 0 && ` ${JSON.stringify(t.arguments)}`} — {t.ok ? "ok" : "recusada"}: {t.summary}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {e.stopped === "max_steps" && (
                  <p className="mt-1 text-xs text-warning">Parou no limite de consultas.</p>
                )}
              </li>
            ))}
            {chat.isPending && <li className="text-sm text-muted-foreground">Consultando os dados…</li>}
          </ol>

          {chat.isError && (
            <ErrorState
              error={chat.error instanceof ApiError ? chat.error : new Error("Falha ao consultar o agente.")}
            />
          )}

          <form onSubmit={onSubmit} className="flex gap-2">
            <Input
              aria-label="Pergunta"
              placeholder={ready ? "Pergunte sobre a sua rede…" : "Agente indisponível"}
              value={text}
              maxLength={2000}
              disabled={!ready || chat.isPending}
              onChange={(e) => setText(e.target.value)}
            />
            <Button type="submit" disabled={!ready || chat.isPending || !text.trim()}>
              Enviar
            </Button>
          </form>
          <p className="text-xs text-muted-foreground">
            Respostas de um modelo de linguagem podem errar: confira nas telas de Dispositivos, Alertas e Network Monitor.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
