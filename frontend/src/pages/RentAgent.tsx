import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, api } from "../lib/api";

export function RentAgent() {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const { checkout_url } = await api.checkout(name.trim());
      // Stripe (or, in local mode, the mock-pay shim) — full-page redirect.
      window.location.href = checkout_url;
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Checkout failed");
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: "32rem" }}>
      <div className="eyebrow">
        <span className="dot" aria-hidden="true" />
        New rental
      </div>
      <h1 style={{ fontSize: "clamp(2rem,5vw,3rem)" }}>
        Rent an <span className="accent">agent</span>
      </h1>
      <p className="lead" style={{ marginBottom: "2rem" }}>
        $4/month, prorated. You'll be taken to checkout, then back here to configure
        and connect it.
      </p>

      <form onSubmit={submit} className="card stack">
        <div>
          <label className="field" htmlFor="dn">
            Agent name
          </label>
          <input
            id="dn"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="raj-alpha"
            required
            minLength={1}
            maxLength={255}
          />
        </div>
        {err && <div className="notice">{err}</div>}
        <div className="row" style={{ gap: "0.75rem" }}>
          <button className="btn btn-primary" disabled={busy || !name.trim()}>
            {busy ? "Redirecting…" : "Continue to checkout"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => nav("/dashboard")}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
