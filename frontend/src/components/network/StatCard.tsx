import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";

export function StatCard({
  title,
  value,
  hint,
  loading,
  className,
  icon,
}: {
  title: string;
  value: ReactNode;
  hint?: ReactNode;
  loading?: boolean;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <div className={cn("text-2xl font-semibold tabular-nums", className)}>{value}</div>
        )}
        {hint && !loading && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export function deltaLabel(delta: number | null, unit: string, lowerIsBetter: boolean): ReactNode {
  if (delta === null) return "sem período anterior para comparar";
  if (delta === 0) return "igual ao período anterior";
  const good = lowerIsBetter ? delta < 0 : delta > 0;
  return (
    <span className={good ? "text-success" : "text-warning"}>
      {delta > 0 ? "+" : ""}
      {delta.toFixed(1)}
      {unit} vs período anterior
    </span>
  );
}
