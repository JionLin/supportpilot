import Link from "next/link";

import { cn } from "@/lib/utils";

type SiteNavProps = {
  variant?: "landing" | "app";
  className?: string;
};

const links = [
  { href: "/chat", label: "Chat" },
  { href: "/admin/knowledge", label: "Admin" },
];

export function SiteNav({ variant = "app", className }: SiteNavProps) {
  return (
    <nav
      className={cn(
        "flex items-center justify-between gap-4",
        variant === "landing" ? "text-ink/80" : "border-b border-border/80 bg-surface/80 backdrop-blur",
        className,
      )}
    >
      <Link
        href="/"
        className={cn(
          "font-display text-lg tracking-tight transition-opacity hover:opacity-80",
          variant === "landing" ? "text-ink" : "px-4 py-3 text-brand sm:px-6",
        )}
      >
        SupportPilot
      </Link>
      <div
        className={cn(
          "flex items-center gap-1 text-sm",
          variant === "app" && "px-4 py-2 sm:px-6",
        )}
      >
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-mist hover:text-foreground"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
