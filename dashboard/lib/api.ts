// FastAPI backend के साथ बात करने वाला छोटा client.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Task = {
  id: string;
  title: string;
  agent_type: string;
  payload: Record<string, unknown>;
  priority: number;
  status: "pending" | "in_progress" | "completed" | "failed";
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
  updated_at?: string;
};

export type AgentInfo = { agent_type: string; role: string };

export type Lead = {
  id: string;
  name?: string;
  email?: string;
  phone?: string;
  company?: string;
  message?: string;
  service_slug?: string;
  source: string;
  status: string;
  created_at: string;
};

export type RootInfo = {
  name: string;
  version: string;
  supabase_configured: boolean;
  llm_configured: boolean;
  agents: string[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  info: () => req<RootInfo>("/"),
  agents: () => req<{ registry: AgentInfo[]; db_agents: unknown[] }>("/agents"),
  tasks: (status?: string) =>
    req<Task[]>(`/tasks${status ? `?status=${status}` : ""}`),
  leads: () => req<Lead[]>("/leads"),
  createTask: (body: {
    title: string;
    agent_type: string;
    payload?: Record<string, unknown>;
    priority?: number;
  }) => req<Task>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  runTask: (id: string) =>
    req<{ status: string; task_id: string }>(`/tasks/${id}/run`, {
      method: "POST",
    }),
  tick: () =>
    req<{ processed: number }>("/orchestrator/tick", { method: "POST" }),
};

export { API_URL };
