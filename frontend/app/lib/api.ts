// Client for the Memory Leak / Glasshouse backend.
//
// Defaults to the same-origin "/backend" path, which next.config.ts rewrites to
// the real backend (localhost:8000 by default). A same-origin relative path
// means the browser talks only to whatever origin served the app — localhost or
// an ngrok tunnel — and the Next server proxies to the backend, so it works over
// ngrok with a single tunnel and no CORS.
//
// Set NEXT_PUBLIC_API_BASE to hit a backend directly instead (must be an
// absolute URL the browser can reach, and CORS-enabled).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/backend";

export type Role = "user" | "assistant";
export type Tier = "A" | "B" | "C" | "D";
export type Confidence = "low" | "medium" | "high";
export type AnalysisMode = "conservative" | "speculative";

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp?: string | null;
}

export interface Conversation {
  conversation_id: string;
  title: string;
  messages: Message[];
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  preview: string;
}

export interface Account {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface ProjectMemory {
  project_id: string;
  memory: string;
}

export interface ProviderMemory {
  conversations_memory?: string | null;
  project_memories: ProjectMemory[];
}

export interface ParseResponse {
  format: string;
  conversations: Conversation[];
  summaries: ConversationSummary[];
  account?: Account | null;
  memory?: ProviderMemory | null;
}

export interface Evidence {
  message_id: string;
  quote: string;
}

export type Subject = "self" | "third_party";

export interface Inference {
  subject?: Subject;
  category_id: string;
  tier: Tier;
  claim: string;
  confidence: Confidence;
  reasoning: string;
  evidence: Evidence[];
}

export interface AnalyzeMeta {
  count: number;
  model: string;
  mode: AnalysisMode;
  mock: boolean;
  tier_counts?: Record<string, number>;
  tier_errors?: Record<string, string>;
  dropped_evidence: number;
  dropped_inferences: number;
}

export interface ExportFiles {
  /** conversations.json, a full .zip export, or a single conversations.json */
  file: File;
  /** users.json — only used by the "folder" upload path */
  users?: File;
  /** memories.json — only used by the "folder" upload path */
  memories?: File;
}

export interface ParseOptions {
  format?: string; // auto | claude | chatgpt | generic
  humanOnly?: boolean; // default true
}

/** POST /parse — upload an export and get canonical conversations back. */
export async function parseExport(
  files: ExportFiles,
  options: ParseOptions = {},
): Promise<ParseResponse> {
  const form = new FormData();
  form.append("file", files.file, files.file.name);
  form.append("format", options.format ?? "auto");
  form.append("human_only", String(options.humanOnly ?? true));
  if (files.users) form.append("users", files.users, files.users.name);
  if (files.memories) form.append("memories", files.memories, files.memories.name);

  const res = await fetch(`${API_BASE}/parse`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(`/parse failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as ParseResponse;
}

export interface AnalyzeHandlers {
  onMeta?: (meta: AnalyzeMeta) => void;
  onInference?: (inference: Inference) => void;
  onError?: (message: string) => void;
  onDone?: (data: { count: number }) => void;
}

export interface AnalyzeOptions {
  conversationId?: string;
  mode?: AnalysisMode;
}

/**
 * POST /analyze — stream the dossier via SSE. Resolves with the full list of
 * inferences once the stream ends. Uses fetch (not EventSource) because the
 * endpoint is a POST.
 */
export async function analyze(
  messages: Message[],
  handlers: AnalyzeHandlers = {},
  options: AnalyzeOptions = {},
): Promise<Inference[]> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages,
      conversation_id: options.conversationId ?? null,
      mode: options.mode ?? "conservative",
    }),
  });
  if (!res.ok || !res.body) {
    const detail = await safeDetail(res);
    throw new Error(`/analyze failed (${res.status}): ${detail}`);
  }

  const inferences: Inference[] = [];
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleBlock = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) return;

    const data = JSON.parse(dataLines.join("\n"));
    if (event === "meta") handlers.onMeta?.(data as AnalyzeMeta);
    else if (event === "inference") {
      inferences.push(data as Inference);
      handlers.onInference?.(data as Inference);
    } else if (event === "error") handlers.onError?.(data.message);
    else if (event === "done") handlers.onDone?.(data);
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      handleBlock(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
    }
  }
  if (buffer.trim()) handleBlock(buffer);

  return inferences;
}

async function safeDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
  } catch {
    return res.statusText;
  }
}
