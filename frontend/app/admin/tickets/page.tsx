"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { type Ticket, listTickets, updateTicketStatus } from "@/lib/api";

const STATUSES = ["open", "in_progress", "resolved"] as const;

export default function TicketsAdminPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await listTickets();
    setTickets(data.tickets);
  }, []);

  useEffect(() => {
    void refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  return (
    <div className="space-y-4 animate-fade-in">
      <h1 className="text-xl font-semibold">Handoff tickets</h1>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <ul className="space-y-3">
        {tickets.map((ticket) => (
          <li
            key={ticket.id}
            className="rounded-lg border border-border bg-surface p-4 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">{ticket.id}</p>
              <span className="rounded bg-mist px-2 py-0.5 text-xs">
                {ticket.status}
              </span>
            </div>
            <p className="mt-1 text-muted-foreground">
              {ticket.reason} · {ticket.priority}
            </p>
            <p className="mt-2">{ticket.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {STATUSES.map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant={ticket.status === status ? "default" : "outline"}
                  onClick={async () => {
                    await updateTicketStatus(ticket.id, status);
                    await refresh();
                  }}
                >
                  {status}
                </Button>
              ))}
            </div>
          </li>
        ))}
        {tickets.length === 0 ? (
          <li className="text-sm text-muted-foreground">No tickets yet.</li>
        ) : null}
      </ul>
    </div>
  );
}
