"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type AdminSettings,
  getAdminSettings,
  updateMockChaos,
} from "@/lib/api";

export default function SettingsAdminPage() {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [failureRate, setFailureRate] = useState(0);
  const [latencyMs, setLatencyMs] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getAdminSettings()
      .then((data) => {
        setSettings(data);
        setFailureRate(data.mock_failure_rate);
        setLatencyMs(data.mock_latency_ms);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (!settings && !error) {
    return <p className="text-sm text-muted-foreground">Loading settings…</p>;
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <section className="space-y-2">
        <h1 className="text-xl font-semibold">Settings</h1>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {settings ? (
          <dl className="grid gap-2 rounded-lg border border-border bg-surface p-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Model</dt>
              <dd className="font-medium">{settings.llm_model}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Base URL</dt>
              <dd className="break-all font-mono text-xs">
                {settings.llm_base_url}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">MAX_STEPS</dt>
              <dd>{settings.max_steps}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">MAX_TOOL_ERRORS</dt>
              <dd>{settings.max_tool_errors}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Request timeout</dt>
              <dd>{settings.request_timeout_s}s</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">RAG distance threshold</dt>
              <dd>{settings.rag_distance_threshold}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Embedding</dt>
              <dd>
                {settings.embedding_model} ({settings.embedding_dim}d)
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Webhook</dt>
              <dd>{settings.webhook_configured ? "configured" : "not set"}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section className="space-y-4 rounded-lg border border-border bg-surface p-4">
        <h2 className="text-lg font-semibold">Mock chaos (demo retries)</h2>
        <label className="block text-sm">
          Failure rate: {failureRate.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={failureRate}
            onChange={(event) => setFailureRate(Number(event.target.value))}
            className="mt-2 w-full"
          />
        </label>
        <label className="block text-sm">
          Latency ms: {latencyMs}
          <input
            type="range"
            min={0}
            max={3000}
            step={50}
            value={latencyMs}
            onChange={(event) => setLatencyMs(Number(event.target.value))}
            className="mt-2 w-full"
          />
        </label>
        <Button
          onClick={async () => {
            setMessage(null);
            setError(null);
            try {
              const updated = await updateMockChaos({
                failure_rate: failureRate,
                latency_ms: latencyMs,
              });
              setMessage(
                `Updated mock chaos → failure ${updated.failure_rate}, latency ${updated.latency_ms}ms`,
              );
            } catch (err) {
              setError(err instanceof Error ? err.message : "Update failed");
            }
          }}
        >
          Apply
        </Button>
        {message ? <p className="text-sm text-brand">{message}</p> : null}
      </section>
    </div>
  );
}
