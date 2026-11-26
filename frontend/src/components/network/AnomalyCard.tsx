import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useAnomalies, useMlStatus } from "@/hooks/useMl";
import { formatDateTime } from "@/utils/format";

const METHOD_LABEL: Record<string, string> = {
  isolation_forest: "Isolation Forest",
  robust_zscore: "estatística robusta (mediana/MAD)",
};

export function AnomalyCard() {
  const status = useMlStatus();
  const anomalies = useAnomalies(24);
  const names = new Map((status.data?.targets ?? []).map((t) => [t.target_id, t.name]));
  const st = status.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Comportamento fora do padrão (últimas 24 h)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {status.isError ? (
          <ErrorState error={status.error} onRetry={() => void status.refetch()} />
        ) : status.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : st && !st.enabled ? (
          <EmptyState title="Detecção de anomalias desligada" hint="Ligue com NG_ML_ENABLED=true." />
        ) : (
          st && (
            <>
              <p className="text-xs text-muted-foreground">
                {st.effective_method
                  ? `Método em uso: ${METHOD_LABEL[st.effective_method] ?? st.effective_method}.`
                  : `Ainda aprendendo: cada destino precisa de ${st.min_windows} janelas de ${st.window_minutes} min (~${Math.round((st.min_windows * st.window_minutes) / 60)} h de medições).`}
                {!st.sklearn_available && " Isolation Forest indisponível (scikit-learn não instalado): usando o método estatístico."}
              </p>
              <ul className="flex flex-wrap gap-2" aria-label="Preparo por destino">
                {st.targets.map((t) => (
                  <li key={t.target_id}>
                    <Badge tone={t.ready ? "success" : "neutral"}>
                      {t.name}: {t.ready ? "pronto" : `${t.windows}/${st.min_windows} janelas`}
                    </Badge>
                  </li>
                ))}
              </ul>
            </>
          )
        )}

        {anomalies.isError ? (
          <ErrorState error={anomalies.error} onRetry={() => void anomalies.refetch()} />
        ) : anomalies.isLoading ? null : (anomalies.data ?? []).length === 0 ? (
          st?.enabled && <EmptyState title="Nenhum desvio detectado" hint="Só há avisos quando uma medição foge do histórico do próprio destino." />
        ) : (
          <ul aria-label="Anomalias detectadas">
            {(anomalies.data ?? []).map((a) => (
              <li key={a.id} className="border-t border-border py-2 text-sm">
                <span className="font-medium">{names.get(a.target_id) ?? `Destino ${a.target_id}`}</span>
                <span className="ml-2 text-xs text-muted-foreground">{formatDateTime(a.window_start)}</span>
                <p className="text-muted-foreground">{a.deviations.join("; ")}</p>
              </li>
            ))}
            <li className="pt-1 text-xs text-muted-foreground">
              Desvios estatísticos do histórico — não indicam a causa nem que algo seja malicioso.
            </li>
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
