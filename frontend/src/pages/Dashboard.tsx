import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { type Agent, api } from "../lib/api";
import { StatusBadge } from "../components/bits";

export function Dashboard() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [params] = useSearchParams();
  const checkout = params.get("checkout");

  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => setAgents([]));
  }, []);

  const total = (agents ?? []).reduce((s, a) => s + a.monthly_cost_cents, 0);

  return (
    <>
      <div className="row between" style={{ marginBottom: "2rem" }}>
        <div>
          <div className="eyebrow">
            <span className="dot" aria-hidden="true" />
            My agents
          </div>
          <h1 style={{ fontSize: "clamp(2rem,5vw,3rem)" }}>Dashboard</h1>
        </div>
        <Link className="btn btn-primary" to="/rent">
          Rent an agent
        </Link>
      </div>

      {checkout && (
        <div
          className={`notice ${checkout === "deployed" ? "accent" : ""}`}
          style={{ marginBottom: "1.5rem" }}
        >
          {checkout === "deployed"
            ? "Payment received — your agent is being deployed."
            : `Checkout: ${checkout}`}
        </div>
      )}

      {agents === null ? (
        <div className="center" style={{ padding: "3rem" }}>
          <div className="spinner" style={{ margin: "0 auto" }} />
        </div>
      ) : agents.length === 0 ? (
        <div className="card center" style={{ padding: "3rem" }}>
          <p className="muted">You have no agents yet.</p>
          <Link className="btn btn-primary" to="/rent">
            Rent your first agent
          </Link>
        </div>
      ) : (
        <>
          <p className="subtle" style={{ marginBottom: "1rem" }}>
            {agents.length} agent{agents.length > 1 ? "s" : ""} · $
            {(total / 100).toFixed(2)}/mo total
          </p>
          <div className="grid cols-3">
            {agents.map((a) => (
              <Link
                key={a.id}
                to={`/agents/${a.id}`}
                className="card hoverable"
                style={{ display: "block" }}
              >
                <div className="row between">
                  <h3 style={{ margin: 0 }}>{a.display_name}</h3>
                  <StatusBadge status={a.status} />
                </div>
                <p className="subtle" style={{ margin: "0.75rem 0 0" }}>
                  ${(a.monthly_cost_cents / 100).toFixed(2)}/mo
                  {a.renewal_date ? ` · renews ${a.renewal_date}` : ""}
                </p>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}
