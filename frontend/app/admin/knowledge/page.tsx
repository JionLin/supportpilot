"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiFetch, type KbDocument } from "@/lib/api";

type SearchHit = {
  document?: string;
  title?: string;
  chunk_id?: string;
  snippet?: string;
  score?: number;
  distance?: number;
};

export default function AdminKnowledgePage() {
  const [docs, setDocs] = useState<KbDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searching, setSearching] = useState(false);

  const loadDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<{ documents: KbDocument[] }>("/api/kb/documents");
      setDocs(data.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  async function onUploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement;
    const file = fileInput.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      await apiFetch("/api/kb/documents", { method: "POST", body });
      form.reset();
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function onIngestUrl(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setUploading(true);
    setError(null);
    try {
      await apiFetch("/api/kb/documents/url", {
        method: "POST",
        body: JSON.stringify({
          url: url.trim(),
          title: urlTitle.trim() || undefined,
        }),
      });
      setUrl("");
      setUrlTitle("");
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "URL ingest failed");
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(id: string) {
    setError(null);
    try {
      await apiFetch(`/api/kb/documents/${id}`, { method: "DELETE" });
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const data = await apiFetch<{ hits: SearchHit[] }>("/api/kb/search", {
        method: "POST",
        body: JSON.stringify({ query: query.trim(), top_k: 5 }),
      });
      setHits(data.hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <header>
        <h1 className="font-display text-3xl text-brand">Knowledge</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload documents, ingest URLs, and test retrieval.
        </p>
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={onUploadFile} className="space-y-3 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Upload file</h2>
          <p className="text-xs text-muted-foreground">PDF, Markdown, or TXT</p>
          <input
            name="file"
            type="file"
            accept=".pdf,.md,.markdown,.txt"
            className="block w-full text-sm"
            required
          />
          <Button type="submit" disabled={uploading}>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </form>

        <form onSubmit={onIngestUrl} className="space-y-3 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">Ingest URL</h2>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-2"
            required
          />
          <input
            value={urlTitle}
            onChange={(e) => setUrlTitle(e.target.value)}
            placeholder="Optional title"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-2"
          />
          <Button type="submit" disabled={uploading || !url.trim()}>
            Ingest URL
          </Button>
        </form>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Documents</h2>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadDocs()}>
            Refresh
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : docs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No documents yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium">{doc.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.source_type} · {doc.status} · {doc.chunk_count ?? 0} chunks
                  </p>
                </div>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => void onDelete(doc.id)}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold">Search test</h2>
        <form onSubmit={onSearch} className="flex flex-col gap-2 sm:flex-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Try a policy question…"
            className="min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-ring focus:ring-2"
          />
          <Button type="submit" disabled={searching || !query.trim()}>
            {searching ? "Searching…" : "Search"}
          </Button>
        </form>
        {hits.length > 0 ? (
          <ul className="space-y-3 pt-2">
            {hits.map((hit, index) => (
              <li key={`${hit.chunk_id ?? index}`} className="rounded-md bg-mist/60 px-3 py-2 text-sm">
                <p className="font-medium">
                  {hit.title ?? hit.document ?? "Hit"}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    {hit.chunk_id}
                    {typeof hit.score === "number"
                      ? ` · score ${hit.score.toFixed(3)}`
                      : typeof hit.distance === "number"
                        ? ` · distance ${hit.distance.toFixed(3)}`
                        : ""}
                  </span>
                </p>
                {hit.snippet ? (
                  <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
                    {hit.snippet}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
