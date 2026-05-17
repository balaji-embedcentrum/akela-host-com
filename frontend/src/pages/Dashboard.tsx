import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { type Agent, api } from "../lib/api";
import { StatusBadge } from "../components/bits";

type Usage = Awaited<ReturnType<typeof api.usage>>;
type Referral = Awaited<ReturnType<typeof api.referral>>;

export function Dashboard() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [ref, setRef] = useState<Referral | null>(null);
  const [params] = useSearchParams();
  const checkout = params.get("checkout");

  useEffect(() => {
    api.referral().then(setRef).catch(() => setRef(null));
    api.listAgents().then(setAgents).catch(() => setAgents([]));
    api.usage().then(setUsage).catch(() => setUsage(null));
  }, []);

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

      {ref && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div className="lbl">Refer &amp; earn</div>
          <p className="subtle" style={{ margin: "0.3rem 0 0.6rem" }}>
            Share your link — you get one free month ($4 credit) when a referred
            user deploys their first agent. {ref.referred_count} referred · $
            {(ref.earned_cents / 100).toFixed(2)} earned.
          </p>
          <div className="cred">
            <code>{`${window.location.origin}/?ref=${ref.code}`}</code>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() =>
                navigator.clipboard?.writeText(
                  `${window.location.origin}/?ref=${ref.code}`,
                )
              }
            >
              Copy
            </button>
          </div>
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
          {usage && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <div className="row between">
                <div>
                  <div className="lbl">This month ({usage.month})</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 700 }}>
                    ${(usage.total_cents / 100).toFixed(2)}
                  </div>
                </div>
                <div className="subtle" style={{ textAlign: "right" }}>
                  {agents.length} agent{agents.length > 1 ? "s" : ""}
                  {usage.credit_cents > 0 && (
                    <div>− ${(usage.credit_cents / 100).toFixed(2)} referral credit</div>
                  )}
                </div>
              </div>
            </div>
          )}
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
