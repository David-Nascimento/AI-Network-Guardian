import "@xyflow/react/dist/style.css";

import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { useTopology } from "@/hooks/useDevices";
import type { Topology as TopologyData, TopologyNode } from "@/types/api";
import { cn } from "@/utils/cn";
import { CATEGORY_LABEL, layoutTopology } from "@/utils/topology";

const STATUS_COLOR = {
  online: "hsl(var(--success))",
  offline: "hsl(var(--danger))",
  unknown: "hsl(var(--muted-foreground))",
} as const;

const KIND_LABEL = { internet: "Internet", gateway: "Gateway", device: "Dispositivo" } as const;

export function toFlow(data: TopologyData): { nodes: Node[]; edges: Edge[] } {
  const positions = new Map(layoutTopology(data.nodes).map((p) => [p.id, p]));
  const nodes: Node[] = data.nodes.map((n) => ({
    id: n.id,
    position: { x: positions.get(n.id)?.x ?? 0, y: positions.get(n.id)?.y ?? 0 },
    data: { label: n.ip && n.ip !== n.label ? `${n.label}\n${n.ip}` : n.label },
    draggable: false,
    style: {
      border: `2px solid ${STATUS_COLOR[n.status]}`,
      borderStyle: n.is_known === false ? "dashed" : "solid",
      background: "hsl(var(--card))",
      color: "hsl(var(--foreground))",
      borderRadius: 8,
      padding: 8,
      fontSize: 12,
      whiteSpace: "pre-line",
      width: 150,
    },
  }));
  const edges: Edge[] = data.edges.map((e) => ({
    id: `${e.source}->${e.target}`,
    source: e.source,
    target: e.target,
    animated: false,
    style: {
      stroke: "hsl(var(--muted-foreground))",
      strokeWidth: e.confidence === "confirmed" ? 2.5 : 1.5,
      strokeDasharray: e.confidence === "confirmed" ? undefined : "6 4",
    },
    markerEnd: { type: MarkerType.ArrowClosed },
  }));
  return { nodes, edges };
}

function Details({ node, data }: { node: TopologyNode; data: TopologyData }) {
  const edge = data.edges.find((e) => e.target === node.id);
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{node.label}</span>
        <Badge tone="network">{KIND_LABEL[node.kind]}</Badge>
        <Badge tone={node.status === "online" ? "success" : node.status === "offline" ? "danger" : "neutral"}>
          {node.status === "online" ? "Online" : node.status === "offline" ? "Offline" : "Sem dados"}
        </Badge>
        {node.is_known === false && <Badge tone="warning">Não reconhecido</Badge>}
      </div>
      {node.ip && <p className="text-muted-foreground">IP {node.ip}</p>}
      {node.category && <p className="text-muted-foreground">{CATEGORY_LABEL[node.category] ?? node.category}</p>}
      {edge && (
        <p>
          <Badge tone={edge.confidence === "confirmed" ? "success" : "neutral"}>
            Ligação {edge.confidence === "confirmed" ? "confirmada" : "inferida"}
          </Badge>{" "}
          <span className="text-muted-foreground">{edge.reason}</span>
        </p>
      )}
    </div>
  );
}

export function Topology() {
  const topology = useTopology();
  const [selected, setSelected] = useState<string | null>(null);
  const flow = useMemo(() => (topology.data ? toFlow(topology.data) : null), [topology.data]);

  if (topology.isError) return <ErrorState error={topology.error} onRetry={() => void topology.refetch()} />;
  const data = topology.data;
  const node = data?.nodes.find((n) => n.id === selected);

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">Topologia</h1>
        <p className="text-sm text-muted-foreground">
          Montada só com o que foi observado. Linhas tracejadas são relações inferidas.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mapa da rede</CardTitle>
          <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label="Legenda">
            <li className="flex items-center gap-1"><span className="inline-block w-6 border-t-2 border-muted-foreground" /> confirmada</li>
            <li className="flex items-center gap-1"><span className="inline-block w-6 border-t-2 border-dashed border-muted-foreground" /> inferida</li>
            <li className="flex items-center gap-1"><span className={cn("inline-block h-3 w-3 rounded-sm border-2 border-dashed border-success")} /> não reconhecido</li>
          </ul>
        </CardHeader>
        <CardContent>
          {topology.isLoading || !flow ? (
            <Skeleton className="h-96 w-full" />
          ) : (
            <div role="group" aria-label="Diagrama da topologia" className="h-[28rem] rounded-md border border-border">
              <ReactFlow
                nodes={flow.nodes}
                edges={flow.edges}
                fitView
                nodesConnectable={false}
                onNodeClick={(_, n) => setSelected(n.id)}
                proOptions={{ hideAttribution: true }}
              >
                <Background />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>
          )}
        </CardContent>
      </Card>

      {data && (
        <Card>
          <CardHeader><CardTitle>{node ? "Detalhes" : "Selecione um item do mapa"}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {node && <Details node={node} data={data} />}
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {data.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}
