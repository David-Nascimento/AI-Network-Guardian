import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useToken } from "@/stores/auth";

export function RequireAuth() {
  const token = useToken();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
