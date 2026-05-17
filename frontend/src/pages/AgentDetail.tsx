import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { type Agent, api } from "../lib/api";
import { CopyField, StatusBadge } from "../components/bits";

export function AgentDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [env, setEnv] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const a = await api.getAgent(id);
    // api_key is returned exactly once — capture it before it's gone.
    if (a.api_key) setApiKey(a.api_key);
    setAgent(a);
  };
  useEffect(() => {
    load().catch(() => nav("/dashboard"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const act = async (fn: () => Promise<Agent>) => {
    setBusy(true);
    try {
      setAgent(await fn());
    } finally {
      setBusy(false);
    }
  };

  const parseEnv = (): Record<string, string> =>
    Object.fromEntries(
      env
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith("#") && l.includes("="))
        .map((l) => {
          const i = l.indexOf("=");
          return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
        }),
    );

  if (!agent)
    return (
      <div className="center" style={{ padding: "5rem" }}>
        <div className="spinner" style={{ margin: "0 auto" }} />
      </div>
    );

  return (
    <div style={{ maxWidth: "44rem" }}>
      <button className="btn btn-ghost btn-sm" onClick={() => nav("/dashboard")}>
        ← Dashboard
      </button>
      <div className="row between" style={{ margin: "1.5rem 0" }}>
        <h1 style={{ fontSize: "clamp(1.8rem,4vw,2.6rem)", margin: 0 }}>
          {agent.display_name}
        </h1>
        <StatusBadge status={agent.status} />
      </div>

      {apiKey && (
        <div className="notice accent" style={{ marginBottom: "1.5rem" }}>
          <strong>Save your API key now.</strong> It is shown only once.
        </div>
      )}

      <div className="card stack" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ margin: 0 }}>Connection info</h3>
        <p className="subtle" style={{ margin: "0 0 0.5rem" }}>
          Paste these into your Akela AI.
        </p>
        {agent.a2a_url && <CopyField label="AKELA_API_URL" value={agent.a2a_url} />}
        {agent.workspace_url && (
          <CopyField label="AKELA_WORKSPACE_URL" value={agent.workspace_url} />
        )}
        {apiKey ? (
          <CopyField label="AKELA_API_KEY" value={apiKey} />
        ) : (
          <div>
            <div className="lbl cred-lbl">AKELA_API_KEY</div>
            <div className="cred">
              <code>•••••••••• (shown once at deploy)</code>
            </div>
          </div>
        )}
      </div>

      <div className="card stack" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ margin: 0 }}>Configuration</h3>
        <p className="subtle" style={{ margin: 0 }}>
          Your <code>.env</code> (LLM keys etc.). Passed straight to the container —
          never stored by us. Redeploying restarts the agent.
        </p>
        <textarea
          className="input"
          value={env}
          onChange={(e) => setEnv(e.target.value)}
          placeholder={"OPENROUTER_API_KEY=sk-...\nGITHUB_TOKEN=ghp_..."}
        />
        <button
          className="btn btn-primary"
          disabled={busy}
          onClick={() => act(() => api.redeploy(agent.id, parseEnv()))}
        >
          Save & redeploy
        </button>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Actions</h3>
        <p className="subtle">
          ${(agent.monthly_cost_cents / 100).toFixed(2)}/mo
          {agent.renewal_date ? ` · renews ${agent.renewal_date}` : ""}
          {" · uptime (30d): "}
          {agent.uptime_pct == null ? "—" : `${agent.uptime_pct}%`}
        </p>
        <div className="row" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
          <button
            className="btn btn-ghost btn-sm"
            disabled={busy}
            onClick={() => act(() => api.stop(agent.id))}
          >
            Stop
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={busy}
            onClick={() => act(() => api.start(agent.id))}
          >
            Start
          </button>
          <button
            className="btn btn-danger btn-sm"
            disabled={busy}
            onClick={() => {
              if (
                confirm(
                  `Cancel "${agent.display_name}"? The agent is recycled and its data wiped.`,
                )
              )
                act(() => api.cancel(agent.id));
            }}
          >
            Cancel rental
          </button>
        </div>
      </div>
    </div>
  );
}
