"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type AdviceRequest,
  type AgentInfo,
  type Deal,
  type FinanceSummary,
  type Lead,
  type Pipeline,
  type RootInfo,
  type Task,
} from "../lib/api";

const STATUSES = ["pending", "in_progress", "completed", "failed"] as const;

function money(n: number, currency = "INR") {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(n || 0);
  } catch {
    return `${n}`;
  }
}

export default function Dashboard() {
  const [info, setInfo] = useState<RootInfo | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [advice, setAdvice] = useState<AdviceRequest[]>([]);
  const [finance, setFinance] = useState<FinanceSummary | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // start-pipeline form
  const [ppTitle, setPpTitle] = useState("");
  const [ppMarket, setPpMarket] = useState("");
  const [ppRegion, setPpRegion] = useState("India");

  // advice answer text per request id
  const [adviceText, setAdviceText] = useState<Record<string, string>>({});

  // add-deal form
  const [dealTitle, setDealTitle] = useState("");
  const [dealRev, setDealRev] = useState(0);
  const [dealCost, setDealCost] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [i, a, t] = await Promise.all([api.info(), api.agents(), api.tasks()]);
      setInfo(i);
      setAgents(a.registry);
      setTasks(t);
      // optional tables — table na ho to chup-chaap ignore
      api.leads().then(setLeads).catch(() => setLeads([]));
      api.pipelines().then(setPipelines).catch(() => setPipelines([]));
      api.advice("pending").then(setAdvice).catch(() => setAdvice([]));
      api.finance().then(setFinance).catch(() => setFinance(null));
      api.deals().then(setDeals).catch(() => setDeals([]));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend se connect nahi hua.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const stats = useMemo(() => {
    const by: Record<string, number> = {};
    for (const s of STATUSES) by[s] = 0;
    for (const t of tasks) by[t.status] = (by[t.status] || 0) + 1;
    return by;
  }, [tasks]);

  async function guarded(fn: () => Promise<void>, errMsg: string) {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : errMsg);
    } finally {
      setBusy(false);
    }
  }

  const handleTick = () => guarded(() => api.tick().then(() => {}), "Orchestrator tick fail.");
  const handleRun = (id: string) =>
    guarded(() => api.runTask(id).then(() => {}), "Task run fail.");

  const handleStartPipeline = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ppTitle.trim()) return;
    return guarded(async () => {
      await api.startPipeline({
        title: ppTitle.trim(),
        start_agent: "research",
        market: ppMarket || undefined,
        region: ppRegion || undefined,
        priority: 7,
      });
      setPpTitle("");
      setPpMarket("");
    }, "Pipeline start nahi hua.");
  };

  const handleAnswer = (a: AdviceRequest, decision: string) =>
    guarded(async () => {
      await api.answerAdvice(a.id, decision, adviceText[a.id] || "");
      setAdviceText((p) => ({ ...p, [a.id]: "" }));
    }, "Advice bhejne me dikkat.");

  const handleAddDeal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dealTitle.trim()) return;
    return guarded(async () => {
      await api.createDeal({
        title: dealTitle.trim(),
        projected_revenue: dealRev,
        projected_cost: dealCost,
      });
      setDealTitle("");
      setDealRev(0);
      setDealCost(0);
    }, "Deal add nahi hua.");
  };

  const cur = finance?.currency || "INR";

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1>AitoTech Command Center</h1>
          <div className="subtitle">
            Workflow, profit aur Sayra ki advice — ek hi jagah
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

      {/* ── Sayra advice inbox (jahan aapki zaroorat hai) ── */}
      {advice.length > 0 && (
        <div className="panel sayra">
          <h2>💬 Sayra ko aapki advice chahiye ({advice.length})</h2>
          {advice.map((a) => (
            <div className="advice" key={a.id}>
              <div className="advice-q">{a.question}</div>
              {a.context && <div className="advice-ctx">{a.context.slice(0, 600)}…</div>}
              <textarea
                placeholder="Aapki advice / instruction agents ke liye (optional)…"
                value={adviceText[a.id] || ""}
                onChange={(e) =>
                  setAdviceText((p) => ({ ...p, [a.id]: e.target.value }))
                }
              />
              <div className="advice-actions">
                {(a.options.length ? a.options : ["Approve & continue", "Reject"]).map(
                  (opt) => (
                    <button
                      key={opt}
                      className={opt.toLowerCase().includes("reject") ? "ghost" : ""}
                      onClick={() => handleAnswer(a, opt)}
                      disabled={busy}
                    >
                      {opt}
                    </button>
                  )
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Profit cards (projected + actual) ── */}
      <div className="stats">
        <div className="stat-card">
          <div className="label">Projected profit</div>
          <div className="value" style={{ color: "var(--accent)" }}>
            {money(finance?.projected_profit || 0, cur)}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Actual profit</div>
          <div className="value" style={{ color: "var(--completed)" }}>
            {money(finance?.actual_profit || 0, cur)}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Actual revenue</div>
          <div className="value">{money(finance?.actual_revenue || 0, cur)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Deals (won)</div>
          <div className="value">
            {finance?.deal_count || 0}{" "}
            <span style={{ fontSize: 14, color: "var(--muted)" }}>
              ({finance?.won_count || 0} won)
            </span>
          </div>
        </div>
      </div>

      {/* ── Workflow timeline (pipelines) ── */}
      <div className="panel" style={{ marginBottom: 20 }}>
        <h2>
          🔄 Workflow — agent pipelines
          <button className="ghost" onClick={refresh} disabled={busy}>
            ↻ Refresh
          </button>
        </h2>
        {pipelines.length === 0 ? (
          <div className="empty">Abhi koi pipeline nahi. Neeche se ek shuru karein →</div>
        ) : (
          pipelines.slice(0, 8).map((p) => (
            <div className="pipeline" key={p.pipeline_id}>
              <div className="pipeline-title">{p.title}</div>
              <div className="flow">
                {p.steps.map((s, i) => (
                  <span key={s.task_id} className="flow-step">
                    <span className={`chip ${s.status}`} title={s.status}>
                      {s.agent_type}
                    </span>
                    {i < p.steps.length - 1 && <span className="arrow">→</span>}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="grid">
        {/* Tasks list */}
        <div className="panel">
          <h2>Tasks</h2>
          {loading ? (
            <div className="empty">Loading…</div>
          ) : tasks.length === 0 ? (
            <div className="empty">Abhi koi task nahi. Side se pipeline shuru karein →</div>
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
                    <button className="ghost" onClick={() => handleRun(t.id)} disabled={busy}>
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

        {/* Sidebar */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="panel">
            <h2>🚀 Naya pipeline shuru karein</h2>
            <form className="create" onSubmit={handleStartPipeline}>
              <div>
                <label>Idea / market</label>
                <input
                  value={ppTitle}
                  onChange={(e) => setPpTitle(e.target.value)}
                  placeholder="jaise: SMB manufacturers ke liye invoice automation"
                  required
                />
              </div>
              <div>
                <label>Market (optional)</label>
                <input
                  value={ppMarket}
                  onChange={(e) => setPpMarket(e.target.value)}
                  placeholder="manufacturing / fintech / healthcare"
                />
              </div>
              <div>
                <label>Region</label>
                <input value={ppRegion} onChange={(e) => setPpRegion(e.target.value)} />
              </div>
              <button type="submit" disabled={busy || !ppTitle.trim()}>
                + Start pipeline (research → … → sales)
              </button>
            </form>
          </div>

          <div className="panel">
            <h2>💰 Deals (profit tracking)</h2>
            <form className="create" onSubmit={handleAddDeal}>
              <div>
                <label>Deal title</label>
                <input
                  value={dealTitle}
                  onChange={(e) => setDealTitle(e.target.value)}
                  placeholder="Acme Pvt Ltd — invoice automation"
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <label>Projected revenue</label>
                  <input
                    type="number"
                    value={dealRev}
                    onChange={(e) => setDealRev(Number(e.target.value))}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label>Projected cost</label>
                  <input
                    type="number"
                    value={dealCost}
                    onChange={(e) => setDealCost(Number(e.target.value))}
                  />
                </div>
              </div>
              <button type="submit" disabled={busy || !dealTitle.trim()}>
                + Add deal
              </button>
            </form>
            <div style={{ marginTop: 12 }}>
              {deals.length === 0 ? (
                <div className="empty">Abhi koi deal nahi.</div>
              ) : (
                deals.slice(0, 6).map((d) => (
                  <div className="agent-row" key={d.id}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</div>
                      <div className="role">
                        proj {money(d.projected_revenue - d.projected_cost, d.currency)} ·
                        actual {money(d.actual_revenue - d.actual_cost, d.currency)}
                      </div>
                    </div>
                    <span className={`badge ${d.status === "won" ? "completed" : "pending"}`}>
                      {d.status}
                    </span>
                  </div>
                ))
              )}
            </div>
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
              <div className="empty">Abhi koi lead nahi — Aitotech connect karein.</div>
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
