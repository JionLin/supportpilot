import { HealthStatus } from "@/components/health-status";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">SupportPilot</h1>
        <p className="text-muted-foreground">
          Customer-support AI agent portfolio demo. Self-built, developed with
          AI-assisted coding. Mock data only.
        </p>
      </div>
      <HealthStatus />
    </main>
  );
}
