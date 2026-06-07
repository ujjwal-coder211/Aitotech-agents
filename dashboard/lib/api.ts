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

export type PipelineStep = {
  task_id: string;
  agent_type: string;
  status: Task["status"];
  created_at: string;
};

export type Pipeline = {
  pipeline_id: string;
  title: string;
  created_at: string;
  steps: PipelineStep[];
};

export type AdviceRequest = {
  id: string;
  task_id?: string;
  pipeline_id?: string;
  agent?: string;
  question: string;
  context?: string;
  options: string[];
  status: "pending" | "answered";
  decision?: string;
  response?: string;
  created_at: string;
};

export type FinanceSummary = {
  currency: string;
  deal_count: number;
  won_count: number;
  projected_revenue: number;
  projected_cost: number;
  projected_profit: number;
  actual_revenue: number;
  actual_cost: number;
  actual_profit: number;
};

export type Deal = {
  id: string;
  title: string;
  currency: string;
  projected_revenue: number;
  projected_cost: number;
  actual_revenue: number;
  actual_cost: number;
  status: string;
  created_at: string;
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

  // workflow + human-in-the-loop + profit
  pipelines: () => req<Pipeline[]>("/pipelines"),
  startPipeline: (body: {
    title: string;
    start_agent?: string;
    market?: string;
    region?: string;
    notes?: string;
    priority?: number;
  }) =>
    req<{ ok: boolean; task_id: string }>("/pipeline", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  advice: (status = "pending") =>
    req<AdviceRequest[]>(`/advice?status=${status}`),
  answerAdvice: (id: string, decision: string, response: string) =>
    req<{ ok: boolean; resumed_tasks: string[]; message: string }>(
      `/advice/${id}/answer`,
      { method: "POST", body: JSON.stringify({ decision, response }) }
    ),
  finance: () => req<FinanceSummary>("/finance/summary"),
  deals: () => req<Deal[]>("/deals"),
  createDeal: (body: {
    title: string;
    projected_revenue?: number;
    projected_cost?: number;
    actual_revenue?: number;
    actual_cost?: number;
    status?: string;
    opportunity_id?: string;
    pipeline_id?: string;
  }) => req<Deal>("/deals", { method: "POST", body: JSON.stringify(body) }),
  updateDeal: (
    id: string,
    body: Partial<{
      projected_revenue: number;
      projected_cost: number;
      actual_revenue: number;
      actual_cost: number;
      status: string;
    }>
  ) => req<Deal>(`/deals/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
};

export { API_URL };
