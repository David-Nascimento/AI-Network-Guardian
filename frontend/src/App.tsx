import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { ApiError } from "@/services/api";
import { Login } from "@/pages/Login";
import { Skeleton } from "@/components/ui/skeleton";

// Páginas com gráficos carregam sob demanda (Recharts fica fora do bundle inicial).
const Dashboard = lazy(() => import("@/pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const Devices = lazy(() => import("@/pages/Devices").then((m) => ({ default: m.Devices })));
const Alerts = lazy(() => import("@/pages/Alerts").then((m) => ({ default: m.Alerts })));
const Guardian = lazy(() => import("@/pages/Guardian").then((m) => ({ default: m.Guardian })));
const Reports = lazy(() => import("@/pages/Reports").then((m) => ({ default: m.Reports })));
const Topology = lazy(() => import("@/pages/Topology").then((m) => ({ default: m.Topology })));
const NetworkMonitor = lazy(() =>
  import("@/pages/NetworkMonitor").then((m) => ({ default: m.NetworkMonitor })),
);

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5_000,
        // Não insiste em erros de cliente (401/403/404/422).
        retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
  });
}

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Skeleton className="h-64 w-full" />}>{children}</Suspense>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<Page><Dashboard /></Page>} />
          <Route path="network" element={<Page><NetworkMonitor /></Page>} />
          <Route path="devices" element={<Page><Devices /></Page>} />
          <Route path="alerts" element={<Page><Alerts /></Page>} />
          <Route path="guardian" element={<Page><Guardian /></Page>} />
          <Route path="reports" element={<Page><Reports /></Page>} />
          <Route path="topology" element={<Page><Topology /></Page>} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={createQueryClient()}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
