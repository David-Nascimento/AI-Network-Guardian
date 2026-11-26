import type { TopologyNode } from "@/types/api";

export interface Positioned {
  id: string;
  x: number;
  y: number;
}

const PER_ROW = 6;
const GAP_X = 190;
const GAP_Y = 110;

/** Internet no topo, gateway abaixo e os dispositivos em grade centralizada sob o gateway. */
export function layoutTopology(nodes: TopologyNode[]): Positioned[] {
  const devices = nodes.filter((n) => n.kind === "device");
  const width = (Math.min(PER_ROW, Math.max(devices.length, 1)) - 1) * GAP_X;
  const centerX = width / 2;
  const out: Positioned[] = [];
  for (const n of nodes) {
    if (n.kind === "internet") out.push({ id: n.id, x: centerX, y: 0 });
    else if (n.kind === "gateway") out.push({ id: n.id, x: centerX, y: GAP_Y });
  }
  devices.forEach((n, i) => {
    const row = Math.floor(i / PER_ROW);
    const inRow = Math.min(PER_ROW, devices.length - row * PER_ROW);
    const rowWidth = (inRow - 1) * GAP_X;
    out.push({
      id: n.id,
      x: centerX - rowWidth / 2 + (i % PER_ROW) * GAP_X,
      y: GAP_Y * 2 + row * GAP_Y,
    });
  });
  return out;
}

export const CATEGORY_LABEL: Record<string, string> = {
  unknown: "Não classificado",
  computer: "Computador",
  smartphone: "Smartphone",
  tv: "Smart TV",
  iot: "IoT",
  network: "Rede",
  printer: "Impressora",
  other: "Outro",
};
