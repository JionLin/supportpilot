"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  type ConversationMessage,
  type TraceStep,
  getConversation,
  getTrace,
} from "@/lib/api";

export default function ConversationDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState("");
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      try {
        const [conversation, trace] = await Promise.all([
          getConversation(id),
          getTrace(id),
        ]);
        setMessages(conversation.messages);
        setStatus(conversation.status);
        setSteps(trace.steps);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    })();
  }, [id]);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold">Conversation</h1>
        <p className="font-mono text-xs text-muted-foreground">{id}</p>
        <p className="text-sm">Status: {status || "…"}</p>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Messages</h2>
        <div className="space-y-2">
          {messages.map((message) => (
            <div
              key={message.id}
              className="rounded-md border border-border bg-surface p-3 text-sm"
            >
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {message.role}
              </p>
              <p className="mt-1 whitespace-pre-wrap">{message.content}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Trace timeline</h2>
        <ol className="space-y-3">
          {steps.map((step) => {
            const hasError = Boolean(step.error);
            return (
              <li
                key={step.id}
                className={`rounded-md border p-3 text-sm ${
                  hasError
                    ? "border-destructive/50 bg-destructive/5"
                    : "border-border bg-surface"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">
                    #{step.step_no} {step.node}
                  </span>
                  {step.tool_name ? (
                    <span className="rounded bg-mist px-1.5 py-0.5 text-xs">
                      {step.tool_name}
                    </span>
                  ) : null}
                  {step.latency_ms != null ? (
                    <span className="text-xs text-muted-foreground">
                      {step.latency_ms} ms
                    </span>
                  ) : null}
                  {step.attempt != null && step.attempt > 1 ? (
                    <span className="text-xs text-destructive">
                      retry #{step.attempt}
                    </span>
                  ) : null}
                  {(step.prompt_tokens || step.completion_tokens) && (
                    <span className="text-xs text-muted-foreground">
                      tokens {step.prompt_tokens ?? 0}/
                      {step.completion_tokens ?? 0}
                    </span>
                  )}
                </div>
                {hasError ? (
                  <pre className="mt-2 overflow-x-auto rounded bg-background p-2 text-xs text-destructive">
                    {JSON.stringify(step.error, null, 2)}
                  </pre>
                ) : null}
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-brand">
                    Input / output JSON
                  </summary>
                  <pre className="mt-1 overflow-x-auto rounded bg-mist p-2 text-xs">
                    {JSON.stringify(
                      { input: step.input, output: step.output },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </li>
            );
          })}
          {steps.length === 0 ? (
            <li className="text-sm text-muted-foreground">
              No trace steps recorded for this conversation yet.
            </li>
          ) : null}
        </ol>
      </section>
    </div>
  );
}
