import { useMutation } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/states";
import { api, ApiError } from "@/services/api";
import { authStore, useToken } from "@/stores/auth";

export function Login() {
  const token = useToken();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () => api.login(username.trim(), password),
    onSuccess: (data) => {
      authStore.setToken(data.access_token);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    },
  });

  if (token) return <Navigate to="/" replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate();
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardContent className="space-y-6 p-6">
          <div className="flex flex-col items-center gap-2 text-center">
            <ShieldCheck className="h-8 w-8 text-primary" aria-hidden />
            <h1 className="text-lg font-semibold">AI Network Guardian</h1>
            <p className="text-sm text-muted-foreground">Entre para acessar o painel</p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Usuário" htmlFor="username">
              <Input id="username" autoComplete="username" autoFocus required value={username}
                onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="Senha" htmlFor="password">
              <Input id="password" type="password" autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </Field>
            {login.error && (
              <p role="alert" className="text-sm text-danger">
                {login.error instanceof ApiError ? login.error.message : "Falha ao entrar."}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? "Entrando…" : "Entrar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
