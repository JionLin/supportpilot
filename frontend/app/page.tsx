import Link from "next/link";

import { SiteNav } from "@/components/site-nav";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="hero-atmosphere absolute inset-0" aria-hidden />
      <div className="hero-grid absolute inset-0" aria-hidden />

      <div className="relative z-10 flex min-h-screen flex-col">
        <div className="mx-auto w-full max-w-6xl px-6 pt-6 sm:px-10">
          <SiteNav variant="landing" />
        </div>

        <section className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-6 pb-20 pt-10 sm:px-10 sm:pb-28 sm:pt-6">
          <div className="max-w-2xl animate-fade-in-up">
            <p className="font-display text-5xl leading-[1.05] tracking-tight text-brand sm:text-7xl">
              SupportPilot
            </p>
            <h1 className="mt-6 max-w-xl text-2xl font-semibold leading-snug text-ink sm:text-3xl">
              Customer support that looks up orders, cites policy, and hands off cleanly.
            </h1>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              A self-built portfolio demo of a LangGraph agent with RAG, tools, and
              streaming chat — mock data only.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="hover-lift">
                <Link href="/chat">Try the demo</Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="hover-lift">
                <Link href="/admin/knowledge">Open admin</Link>
              </Button>
            </div>
          </div>

          <p className="mt-16 max-w-xl animate-fade-in text-sm text-muted-foreground [animation-delay:200ms]">
            Architecture: Next.js UI → FastAPI{" "}
            <code className="rounded bg-surface/70 px-1.5 py-0.5 text-xs">/api/chat</code>{" "}
            → LangGraph agent with tools, pgvector RAG, and mock upstreams.
          </p>
          <p className="mt-3 text-xs uppercase tracking-[0.14em] text-brand/70">
            Self-built demo · mock data
          </p>
        </section>
      </div>
    </main>
  );
}
