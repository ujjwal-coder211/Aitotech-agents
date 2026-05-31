"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type AgentInfo, type Lead, type RootInfo, type Task } from "../lib/api";

const STATUSES = ["pending", "in_progress", "completed", "failed"] as const;

export default function Dashboard() {
  const [info, setInfo] = useState<RootInfo | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // create-task form state
  const [title, setTitle] = useState("");
  const [agentType, setAgentType] = useState("research");
  const [priority, setPriority] = useState(0);
  const [payload, setPayload] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [i, a, t] = await Promise.all([
        api.info(),
        api.agents(),
        api.tasks(),
      ]);
      setInfo(i);
      setAgents(a.registry);
      setTasks(t);
      // leads optional है (table न हो तो fail हो सकता है) — चुपचाप ignore
      api.leads().then(setLeads).catch(() => setLeads([]));
      if (a.registry[0]) setAgentType((prev) => prev || a.registry[0].agent_type);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend से connect नहीं हो पाया।");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000); // हर 5s auto-refresh
    return () => clearInterval(id);
  }, [refresh]);

  const stats = useMemo(() => {
    const by: Record<string, number> = {};
    for (const s of STATUSES) by[s] = 0;
    for (const t of tasks) by[t.status] = (by[t.status] || 0) + 1;
    return by;
  }, [tasks]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      let parsed: Record<string, unknown> = {};
      if (payload.trim()) {
        try {
          parsed = JSON.parse(payload);
        } catch {
          throw new Error("Payload valid JSON नहीं है।");
        }
      }
      await api.createTask({
        title: title.trim(),
        agent_type: agentType,
        priority,
        payload: parsed,
      });
      setTitle("");
      setPayload("");
      setPriority(0);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Task बना नहीं।");
    } finally {
      setBusy(false);
    }
  }

  async function handleTick() {
    setBusy(true);
    try {
      await api.tick();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Orchestrator tick fail।");
    } finally {
      setBusy(false);
    }
  }

  async function handleRun(id: string) {
    setBusy(true);
    try {
      await api.runTask(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Task run fail।");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1>AI Enterprise Dashboard</h1>
          <div className="subtitle">
            Tasks और agents को monitor + trigger करने का control panel
          </div>
        </div>
        <div className="toolbar">
          {info && (
            <>
              <span className={`pill ${info.supabase_configured ? "ok" : "bad"}`}>
                Supabase {info.supabase_configured ? "✓" : "✗"}
              </span>
              <span className={`pill ${info.llm_configured ? "ok" : "bad"}`}>
                LLM {info.llm_configured ? "✓" : "✗"}
              </span>
            </>
          )}
          <button className="ghost" onClick={handleTick} disabled={busy}>
            ⚡ Run orchestrator
          </button>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      <div className="stats">
        <div className="stat-card">
          <div className="label">Total tasks</div>
          <div className="value">{tasks.length}</div>
        </div>
        {STATUSES.map((s) => (
          <div className="stat-card" key={s}>
            <div className="label">{s.replace("_", " ")}</div>
            <div className="value" style={{ color: `var(--${s})` }}>
              {stats[s] || 0}
            </div>
          </div>
        ))}
      </div>

      <div className="grid">
        {/* Tasks list */}
        <div className="panel">
          <h2>
            Tasks
            <button className="ghost" onClick={refresh} disabled={busy}>
              ↻ Refresh
            </button>
          </h2>
          {loading ? (
            <div className="empty">Loading…</div>
          ) : tasks.length === 0 ? (
            <div className="empty">अभी कोई task नहीं है। नीचे से नया बनाएँ →</div>
          ) : (
            tasks.map((t) => (
              <div className="task" key={t.id}>
                <div className="top">
                  <span className="title">{t.title}</span>
                  <span className={`badge ${t.status}`}>{t.status}</span>
                </div>
                <div className="meta">
                  <span className="agent-tag">{t.agent_type}</span>
                  {"  "}priority {t.priority} ·{" "}
                  {new Date(t.created_at).toLocaleString()}
                </div>
                {t.status === "pending" && (
                  <div style={{ marginTop: 10 }}>
                    <button
                      className="ghost"
                      onClick={() => handleRun(t.id)}
                      disabled={busy}
                    >
                      ▶ Run now
                    </button>
                  </div>
                )}
                {t.result?.output != null && (
                  <div className="meta" style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
                    {String(t.result.output).slice(0, 400)}
                  </div>
                )}
                {t.error && (
                  <div className="meta" style={{ color: "var(--failed)", marginTop: 8 }}>
                    {t.error}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Sidebar: create + agents */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="panel">
            <h2>नया Task बनाएँ</h2>
            <form className="create" onSubmit={handleCreate}>
              <div>
                <label>Title</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="जैसे: AI tutoring app के लिए market research"
                  required
                />
              </div>
              <div>
                <label>Agent</label>
                <select
                  value={agentType}
                  onChange={(e) => setAgentType(e.target.value)}
                >
                  {agents.map((a) => (
                    <option key={a.agent_type} value={a.agent_type}>
                      {a.agent_type} — {a.role}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Priority (0-10)</label>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                />
              </div>
              <div>
                <label>Payload (JSON, optional)</label>
                <textarea
                  value={payload}
                  onChange={(e) => setPayload(e.target.value)}
                  placeholder='{"region": "India"}'
                />
              </div>
              <button type="submit" disabled={busy || !title.trim()}>
                + Create task
              </button>
            </form>
          </div>

          <div className="panel">
            <h2>Agents ({agents.length})</h2>
            {agents.length === 0 ? (
              <div className="empty">No agents.</div>
            ) : (
              agents.map((a) => (
                <div className="agent-row" key={a.agent_type}>
                  <span className="agent-tag">{a.agent_type}</span>
                  <span className="role">{a.role}</span>
                </div>
              ))
            )}
          </div>

          <div className="panel">
            <h2>Website Leads ({leads.length})</h2>
            {leads.length === 0 ? (
              <div className="empty">अभी कोई lead नहीं — Aitotech connect करें।</div>
            ) : (
              leads.slice(0, 8).map((l) => (
                <div className="agent-row" key={l.id}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>
                      {l.name || l.email || "Unknown"}
                    </div>
                    <div className="role">
                      {l.source}
                      {l.service_slug ? ` · ${l.service_slug}` : ""}
                    </div>
                  </div>
                  <span className={`badge ${l.status === "new" ? "pending" : "completed"}`}>
                    {l.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
