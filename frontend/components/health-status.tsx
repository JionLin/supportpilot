"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type HealthState = "loading" | "healthy" | "unhealthy";

function resolveApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
}

export function HealthStatus() {
  const [state, setState] = useState<HealthState>("loading");
  const [detail, setDetail] = useState<string>("Checking backend…");

  const checkHealth = useCallback(async () => {
    setState("loading");
    setDetail("Checking backend…");
    try {
      const response = await fetch(`${resolveApiBaseUrl()}/api/health`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setState("unhealthy");
        setDetail(`HTTP ${response.status}`);
        return;
      }
      const body = (await response.json()) as { status?: string };
      if (body.status === "ok") {
        setState("healthy");
        setDetail("Backend /api/health returned ok");
        return;
      }
      setState("unhealthy");
      setDetail("Unexpected health payload");
    } catch (error) {
      setState("unhealthy");
      setDetail(error instanceof Error ? error.message : "Request failed");
    }
  }, []);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const label =
    state === "loading"
      ? "Checking…"
      : state === "healthy"
        ? "healthy"
        : "unhealthy";

  return (
    <div className="flex flex-col items-start gap-4">
      <p className="text-sm text-muted-foreground">
        Backend status:{" "}
        <span
          className={
            state === "healthy"
              ? "font-semibold text-emerald-700"
              : state === "unhealthy"
                ? "font-semibold text-red-700"
                : "font-semibold text-foreground"
          }
        >
          {label}
        </span>
      </p>
      <p className="text-sm text-muted-foreground">{detail}</p>
      <Button type="button" variant="outline" onClick={() => void checkHealth()}>
        Recheck health
      </Button>
    </div>
  );
}
