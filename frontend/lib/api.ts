/** API helpers for SupportPilot frontend. */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const ADMIN_PASSWORD_STORAGE_KEY = "supportpilot-admin-password";

export type Citation = {
  document: string;
  chunk_id: string;
  snippet?: string | null;
};

export type ActionRecord = {
  tool: string;
  status: "success" | "failed" | "skipped";
  summary?: string | null;
};

export type AgentReply = {
  answer: string;
  intent: string;
  actions: ActionRecord[];
  citations: Citation[];
  order_card?: Record<string, unknown> | null;
  needs_human?: boolean;
  ticket_id?: string | null;
  confidence?: number;
  conversation_id?: string;
};

export type ConversationSummary = {
  id: string;
  status: string;
  customer_email?: string | null;
  channel?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  structured?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type TraceStep = {
  id: number;
  run_id: string;
  step_no: number;
  node: string;
  tool_name?: string | null;
  input?: unknown;
  output?: unknown;
  error?: string | null;
  attempt?: number | null;
  latency_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  created_at?: string | null;
};

export type KbDocument = {
  id: string;
  title: string;
  status: string;
  source_type: string;
  chunk_count?: number;
  source_uri?: string | null;
  error?: string | null;
  created_at?: string | null;
};

export type Ticket = {
  id: string;
  conversation_id?: string | null;
  reason?: string | null;
  summary?: string | null;
  priority?: string | null;
  status: string;
  created_at?: string | null;
};

export type AdminSettings = {
  llm_model: string;
  llm_base_url: string;
  embedding_model: string;
  embedding_dim: number;
  max_steps: number;
  max_tool_errors: number;
  request_timeout_s: number;
  rag_distance_threshold: number;
  mock_latency_ms: number;
  mock_failure_rate: number;
  webhook_configured: boolean;
};

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function getStoredAdminPassword(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ADMIN_PASSWORD_STORAGE_KEY);
}

export function getAdminPassword(): string | null {
  const stored = getStoredAdminPassword();
  if (stored) return stored;
  return process.env.NEXT_PUBLIC_ADMIN_PASSWORD ?? null;
}

export function setAdminPassword(password: string): void {
  sessionStorage.setItem(ADMIN_PASSWORD_STORAGE_KEY, password);
}

export function clearAdminPassword(): void {
  sessionStorage.removeItem(ADMIN_PASSWORD_STORAGE_KEY);
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
      detail?: { code?: string; message?: string } | string;
      message?: string;
      code?: string;
    };
    if (body.error?.message) {
      return new ApiError(body.error.message, response.status, body.error.code);
    }
    if (typeof body.detail === "object" && body.detail !== null) {
      return new ApiError(
        body.detail.message ?? response.statusText,
        response.status,
        body.detail.code,
      );
    }
    if (typeof body.detail === "string") {
      return new ApiError(body.detail, response.status);
    }
    return new ApiError(
      body.message ?? response.statusText,
      response.status,
      body.code,
    );
  } catch {
    return new ApiError(response.statusText || "Request failed", response.status);
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  options?: { admin?: boolean },
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (options?.admin) {
    const password = getAdminPassword();
    if (password) {
      headers.set("X-Admin-Password", password);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export type SseHandlers = {
  onToken?: (text: string) => void;
  onToolStart?: (payload: { tool?: string; summary?: string }) => void;
  onToolEnd?: (payload: {
    tool?: string;
    status?: string;
    summary?: string;
  }) => void;
  onCitation?: (citation: Citation) => void;
  onFinal?: (reply: AgentReply) => void;
  onError?: (payload: { code?: string; message?: string }) => void;
};

/** Stream POST /api/chat with Accept: text/event-stream via fetch + ReadableStream. */
export async function streamChat(
  body: { conversation_id?: string | null; message: string },
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      conversation_id: body.conversation_id ?? undefined,
      message: body.message,
    }),
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseError(response);
  }
  if (!response.body) {
    throw new ApiError("No response body", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatchSseEvent(rawEvent, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    dispatchSseEvent(buffer, handlers);
  }
}

function dispatchSseEvent(rawEvent: string, handlers: SseHandlers): void {
  const lines = rawEvent.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return;
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  } catch {
    return;
  }

  switch (event) {
    case "token":
      handlers.onToken?.(String(payload.text ?? ""));
      break;
    case "tool_start":
      handlers.onToolStart?.(payload as { tool?: string; summary?: string });
      break;
    case "tool_end":
      handlers.onToolEnd?.(
        payload as { tool?: string; status?: string; summary?: string },
      );
      break;
    case "citation":
      handlers.onCitation?.(payload as Citation);
      break;
    case "final":
      handlers.onFinal?.(payload as AgentReply);
      break;
    case "error":
      handlers.onError?.(payload as { code?: string; message?: string });
      break;
    default:
      break;
  }
}

export function toolStatusLabel(tool?: string): string {
  switch (tool) {
    case "get_order":
      return "Looking up order…";
    case "get_shipment":
    case "track_shipment":
      return "Checking shipment…";
    case "search_knowledge_base":
      return "Searching knowledge base…";
    case "check_availability":
      return "Checking availability…";
    case "book_appointment":
      return "Booking appointment…";
    case "create_return_request":
      return "Creating return request…";
    case "handoff_to_human":
      return "Creating handoff ticket…";
    case "upsert_crm_contact":
      return "Updating CRM…";
    default:
      return tool ? `Running ${tool}…` : "Working…";
  }
}

export async function listConversations() {
  return apiFetch<{ total: number; items: ConversationSummary[] }>(
    "/api/conversations",
  );
}

export async function getConversation(id: string) {
  return apiFetch<{
    id: string;
    status: string;
    messages: ConversationMessage[];
  }>(`/api/conversations/${id}`);
}

export async function getTrace(id: string) {
  return apiFetch<{ conversation_id: string; steps: TraceStep[] }>(
    `/api/conversations/${id}/trace`,
  );
}

export async function listKbDocuments() {
  return apiFetch<{ documents: KbDocument[] }>("/api/kb/documents");
}

export async function uploadKbFile(file: File, title?: string) {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  return apiFetch<{ id: string; status: string }>("/api/kb/documents", {
    method: "POST",
    body: form,
  });
}

export async function ingestKbUrl(url: string, title?: string) {
  return apiFetch<{ id: string; status: string }>("/api/kb/documents/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
  });
}

export async function deleteKbDocument(id: string) {
  return apiFetch<void>(`/api/kb/documents/${id}`, { method: "DELETE" });
}

export async function searchKb(query: string, topK = 5) {
  return apiFetch<{ hits: Array<Record<string, unknown>> }>("/api/kb/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

export async function listTickets() {
  return apiFetch<{ tickets: Ticket[] }>("/api/tickets");
}

export async function updateTicketStatus(
  id: string,
  status: "open" | "in_progress" | "resolved",
) {
  return apiFetch<Ticket>(`/api/tickets/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function getAdminSettings() {
  return apiFetch<AdminSettings>("/api/admin/settings", {}, { admin: true });
}

export async function updateMockChaos(body: {
  latency_ms?: number;
  failure_rate?: number;
}) {
  return apiFetch<{ latency_ms: number; failure_rate: number }>(
    "/api/admin/mock-chaos",
    { method: "PUT", body: JSON.stringify(body) },
    { admin: true },
  );
}
