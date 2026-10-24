"use client";

import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ApiError,
  apiFetch,
  clearAdminPassword,
  getAdminPassword,
  setAdminPassword,
} from "@/lib/api";

type AdminGateProps = {
  children: ReactNode;
};

export function AdminGate({ children }: AdminGateProps) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const existing = getAdminPassword();
    if (!existing) {
      setReady(true);
      return;
    }
    void (async () => {
      try {
        await apiFetch("/api/admin/settings", {}, { admin: true });
        setAuthed(true);
      } catch {
        clearAdminPassword();
      } finally {
        setReady(true);
      }
    })();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setChecking(true);
    setError(null);
    setAdminPassword(password.trim());
    try {
      await apiFetch("/api/admin/settings", {}, { admin: true });
      setAuthed(true);
    } catch (err) {
      clearAdminPassword();
      if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect admin password.");
      } else {
        setError(err instanceof Error ? err.message : "Could not verify password.");
      }
    } finally {
      setChecking(false);
    }
  }

  if (!ready) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Checking admin access…
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="mx-auto flex min-h-[50vh] w-full max-w-md flex-col justify-center px-4 py-12 animate-fade-in">
        <p className="font-display text-3xl text-brand">SupportPilot</p>
        <h1 className="mt-2 text-xl font-semibold text-foreground">Admin access</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Enter the admin password. It is sent as{" "}
          <code className="rounded bg-mist px-1 py-0.5 text-xs">X-Admin-Password</code>{" "}
          and kept in sessionStorage for this tab.
        </p>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted-foreground">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-2"
              autoComplete="current-password"
              required
            />
          </label>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <Button type="submit" disabled={checking || !password.trim()}>
            {checking ? "Verifying…" : "Unlock admin"}
          </Button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
