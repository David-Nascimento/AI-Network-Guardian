import { Activity, Bell, Bot, FileText, LayoutDashboard, Laptop, Network, LogOut, Moon, PanelLeftClose, PanelLeftOpen, ShieldCheck, Sun } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { StatusBadge } from "@/components/network/StatusBadge";
import { Button } from "@/components/ui/button";
import { useAlertSummary } from "@/hooks/useAlerts";
import { useLogout, useMe } from "@/hooks/useAuth";
import { useLiveEvents } from "@/hooks/useLiveEvents";
import { useNetworkStatus } from "@/hooks/useNetwork";
import { useLiveState } from "@/stores/live";
import { themeStore, useTheme } from "@/stores/theme";
import { cn } from "@/utils/cn";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/network", label: "Network Monitor", icon: Activity, end: false },
  { to: "/devices", label: "Dispositivos", icon: Laptop, end: false },
  { to: "/topology", label: "Topologia", icon: Network, end: false },
  { to: "/alerts", label: "Alertas", icon: Bell, end: false },
  { to: "/guardian", label: "AI Guardian", icon: Bot, end: false },
  { to: "/reports", label: "Relatórios", icon: FileText, end: false },
] as const;

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const theme = useTheme();
  const logout = useLogout();
  const { data: me } = useMe();
  const { data: status } = useNetworkStatus();
  const { data: alertSummary } = useAlertSummary();
  const live = useLiveState();
  useLiveEvents();
  const unread = alertSummary?.new ?? 0;

  return (
    <div className="flex min-h-screen">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
      >
        Ir para o conteúdo
      </a>
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-border bg-card transition-[width]",
          collapsed ? "w-16" : "w-56",
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <ShieldCheck className="h-5 w-5 shrink-0 text-primary" aria-hidden />
          {!collapsed && <span className="truncate text-sm font-semibold">AI Network Guardian</span>}
        </div>
        <nav aria-label="Principal" className="flex flex-1 flex-col gap-1 p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={label}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-muted",
                  isActive ? "bg-muted font-medium text-primary" : "text-muted-foreground",
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed && <span>{label}</span>}
              {to === "/alerts" && unread > 0 && (
                <span
                  aria-label={`${unread} alertas novos`}
                  className="ml-auto rounded-full bg-danger px-1.5 text-[11px] font-semibold text-white"
                >
                  {unread}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start"
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            {!collapsed && "Recolher"}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-3 border-b border-border px-4 sm:px-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            Conexão <StatusBadge state={status?.state ?? "unknown"} />
            <span
              className="ml-2 text-xs"
              title={live === "live" ? "Eventos em tempo real (WebSocket)" : "Sem tempo real: atualizando por consulta periódica"}
            >
              {live === "live" ? "● Ao vivo" : live === "connecting" ? "○ Conectando…" : "○ Atualização periódica"}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="mr-2 hidden text-sm text-muted-foreground sm:inline">{me?.username}</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema escuro"}
              onClick={() => themeStore.set(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="icon" aria-label="Sair" onClick={logout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <main id="conteudo" className="flex-1 space-y-6 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
