"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type ConversationSummary, listConversations } from "@/lib/api";

export default function ConversationsAdminPage() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listConversations()
      .then((data) => setItems(data.items))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-xl font-semibold">Conversations</h1>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={`/admin/conversations/${item.id}`}
              className="flex flex-col gap-1 px-4 py-3 transition hover:bg-mist sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="font-mono text-xs sm:text-sm">{item.id}</span>
              <span className="text-sm text-muted-foreground">
                {item.status}
                {item.customer_email ? ` · ${item.customer_email}` : ""}
              </span>
            </Link>
          </li>
        ))}
        {items.length === 0 ? (
          <li className="px-4 py-6 text-sm text-muted-foreground">
            No conversations yet. Try the chat demo first.
          </li>
        ) : null}
      </ul>
    </div>
  );
}
