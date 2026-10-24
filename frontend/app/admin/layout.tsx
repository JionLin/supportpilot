import type { ReactNode } from "react";
import Link from "next/link";

import { AdminGate } from "@/components/admin-gate";
import { SiteFooter } from "@/components/site-footer";
import { SiteNav } from "@/components/site-nav";

const adminLinks = [
  { href: "/admin/knowledge", label: "Knowledge" },
  { href: "/admin/conversations", label: "Conversations" },
  { href: "/admin/tickets", label: "Tickets" },
  { href: "/admin/settings", label: "Settings" },
];

export default function AdminLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteNav />
      <div className="border-b border-border/70 bg-surface/60">
        <div className="mx-auto flex w-full max-w-6xl gap-1 overflow-x-auto px-4 py-2 sm:px-6">
          {adminLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="shrink-0 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-mist hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <AdminGate>{children}</AdminGate>
      </div>
      <SiteFooter sticky />
    </div>
  );
}
