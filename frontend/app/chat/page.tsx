"use client";

import { useCallback, useRef, useState } from "react";

import { SiteFooter } from "@/components/site-footer";
import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";
import {
  type AgentReply,
  type Citation,
  streamChat,
  toolStatusLabel,
} from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  orderCard?: Record<string, unknown> | null;
  ticketId?: string | null;
};

const EXAMPLES = [
  "What is your return policy?",
  "Where is order A1001? email jane@example.com",
  "I want to return order A1003, email sam@example.com",
  "Book a call-back for jane@example.com tomorrow",
  "I need to talk to a human",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [handedOff, setHandedOff] = useState(false);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastUserMessage = useRef("");

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming || handedOff) return;

      lastUserMessage.current = trimmed;
      setError(null);
      setToolStatus(null);
      setStreaming(true);
      setInput("");
      const userId = `u-${Date.now()}`;
      const assistantId = `a-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: trimmed },
        { id: assistantId, role: "assistant", content: "" },
      ]);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          { conversation_id: conversationId, message: trimmed },
          {
            onToken: (chunk) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + chunk }
                    : m,
                ),
              );
            },
            onToolEnd: (payload) => {
              setToolStatus(toolStatusLabel(payload.tool));
            },
            onCitation: (citation) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        citations: [...(m.citations ?? []), citation],
                      }
                    : m,
                ),
              );
            },
            onFinal: (reply: AgentReply) => {
              if (reply.conversation_id) {
                setConversationId(reply.conversation_id);
              }
              setToolStatus(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: reply.answer || m.content,
                        citations: reply.citations?.length
                          ? reply.citations
                          : m.citations,
                        orderCard: reply.order_card,
                        ticketId: reply.ticket_id,
                      }
                    : m,
                ),
              );
              if (reply.needs_human || reply.ticket_id) {
                setHandedOff(true);
                setTicketId(reply.ticket_id ?? null);
              }
            },
            onError: (payload) => {
              setError(payload.message ?? "Chat stream error");
            },
          },
          controller.signal,
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      } finally {
        setStreaming(false);
        setToolStatus(null);
      }
    },
    [conversationId, handedOff, streaming],
  );

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-6 sm:flex-row sm:px-6">
        <aside className="w-full shrink-0 sm:w-56">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Try these
          </p>
          <div className="flex flex-wrap gap-2 sm:flex-col">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                disabled={streaming || handedOff}
                onClick={() => void send(example)}
                className="rounded-md border border-border bg-surface px-3 py-2 text-left text-sm text-foreground transition hover:border-brand hover:bg-brand-soft disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
        </aside>

        <section className="flex min-h-[70vh] flex-1 flex-col rounded-xl border border-border bg-surface shadow-sm">
          <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
            {messages.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Ask about policies, look up a seed order, book a call-back, or
                request a human handoff.
              </p>
            )}
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[90%] rounded-lg bg-brand px-3 py-2 text-sm text-primary-foreground"
                    : "mr-auto max-w-[90%] space-y-2 rounded-lg bg-mist px-3 py-2 text-sm text-foreground"
                }
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
                {message.orderCard ? (
                  <OrderCard data={message.orderCard} />
                ) : null}
                {message.citations && message.citations.length > 0 ? (
                  <CitationsPanel citations={message.citations} />
                ) : null}
              </div>
            ))}
            {toolStatus ? (
              <p className="animate-pulse-soft text-xs text-brand">{toolStatus}</p>
            ) : null}
          </div>

          {handedOff ? (
            <div className="border-t border-border bg-brand-soft px-4 py-3 text-sm">
              Handed off to a human
              {ticketId ? (
                <>
                  {" "}
                  — ticket <strong>{ticketId}</strong>
                </>
              ) : null}
              . Input is disabled for this conversation.
            </div>
          ) : null}

          {error ? (
            <div className="flex items-center justify-between gap-3 border-t border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <span>{error}</span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void send(lastUserMessage.current)}
              >
                Retry
              </Button>
            </div>
          ) : null}

          <form
            className="flex gap-2 border-t border-border p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void send(input);
            }}
          >
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={streaming || handedOff}
              placeholder={
                handedOff ? "Conversation handed off" : "Ask SupportPilot…"
              }
              className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-1 disabled:opacity-50"
            />
            <Button type="submit" disabled={streaming || handedOff || !input.trim()}>
              Send
            </Button>
          </form>
        </section>
      </div>
      <SiteFooter />
    </div>
  );
}

function OrderCard({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="mt-2 rounded-md border border-border bg-surface p-3 text-xs text-foreground">
      <p className="font-semibold">Order {String(data.order_id ?? "")}</p>
      <p>Status: {String(data.status ?? "unknown")}</p>
      {data.tracking_number ? (
        <p>Tracking: {String(data.tracking_number)}</p>
      ) : null}
      {data.total_cents != null ? (
        <p>
          Total: ${(Number(data.total_cents) / 100).toFixed(2)}{" "}
          {String(data.currency ?? "USD")}
        </p>
      ) : null}
    </div>
  );
}

function CitationsPanel({ citations }: { citations: Citation[] }) {
  return (
    <details className="mt-2 rounded-md border border-border bg-surface/80 p-2 text-xs">
      <summary className="cursor-pointer font-medium text-brand">
        Sources ({citations.length})
      </summary>
      <ul className="mt-2 space-y-2">
        {citations.map((citation) => (
          <li key={`${citation.document}-${citation.chunk_id}`}>
            <p className="font-medium">{citation.document}</p>
            {citation.snippet ? (
              <p className="text-muted-foreground">{citation.snippet}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
