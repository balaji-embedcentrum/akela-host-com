import { useEffect, useState } from "react";

import { type FleetStats, api } from "../lib/api";
import { useAuth } from "../lib/auth";

export function Landing() {
  const { user } = useAuth();
  const [fleet, setFleet] = useState<FleetStats | null>(null);

  useEffect(() => {
    api.fleetStats().then(setFleet).catch(() => setFleet(null));
  }, []);

  const ref = new URLSearchParams(window.location.search).get("ref") || undefined;
  const cta = user ? "/dashboard" : api.loginUrl("mock", "/dashboard", ref);

  return (
    <>
      <header className="hero">
        <div className="eyebrow">
          <span className="dot" aria-hidden="true" />
          {fleet
            ? `${fleet.available}/${fleet.total} agents available`
            : "Persistent AI agents"}
        </div>
        <h1>
          Rent <span className="accent">Hermes</span> agents. $4 a month.
        </h1>
        <p className="lead">
          Persistent, fully-owned AI agents on our infrastructure.{" "}
          <strong>You bring the keys, we run the box.</strong> Plug them into your own
          self-hosted Akela AI and go.
        </p>
        <div className="hero-actions" style={{ display: "flex", gap: "0.75rem", marginTop: "2rem" }}>
          <a className="btn btn-primary" href={cta}>
            {user ? "Go to dashboard" : "Get started"}
          </a>
          <a className="btn btn-ghost" href="#how">
            How it works
          </a>
        </div>
      </header>

      <section className="block" id="how">
        <div className="section-grid">
          <div className="section-label">How it works</div>
          <div>
            <h2>
              Three steps to a <span className="accent">running agent.</span>
            </h2>
            <div className="grid cols-3" style={{ marginTop: "1.5rem" }}>
              {[
                ["1 · Rent", "Sign in, pick a name, subscribe for $4/mo. Prorated."],
                ["2 · Configure", "Upload your own .env (LLM keys). Never stored by us."],
                ["3 · Connect", "Copy the A2A + Workspace URLs and API key into Akela AI."],
              ].map(([t, d]) => (
                <div className="card" key={t}>
                  <h3 style={{ margin: "0 0 0.5rem" }}>{t}</h3>
                  <p className="muted" style={{ margin: 0 }}>
                    {d}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="block" id="pricing">
        <div className="section-grid">
          <div className="section-label">Pricing</div>
          <div>
            <h2>
              One price. <span className="accent">$4 / month</span> per agent.
            </h2>
            <p className="muted">
              Prorated on signup. Cancel anytime — your agent runs until the period
              ends, then the slot is recycled and data wiped within 30 days.
            </p>
            <a className="btn btn-primary" href={cta} style={{ marginTop: "1rem" }}>
              {user ? "Rent an agent" : "Get started"}
            </a>
          </div>
        </div>
      </section>

      <section className="block" id="faq">
        <div className="section-grid">
          <div className="section-label">FAQ</div>
          <div className="stack">
            {[
              [
                "Do you store my API keys?",
                "No. Your .env is pushed to the agent host and embedded in the container at deploy time — never written to any database.",
              ],
              [
                "What do I connect it to?",
                "Your own self-hosted Akela AI. We host the agent; you drive it.",
              ],
              [
                "Which models?",
                "Whatever your keys support (OpenRouter, Google, HF, …). You bring the LLM access.",
              ],
            ].map(([q, a]) => (
              <div className="card" key={q}>
                <h3 style={{ margin: "0 0 0.4rem", fontSize: "1.05rem" }}>{q}</h3>
                <p className="muted" style={{ margin: 0 }}>
                  {a}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
