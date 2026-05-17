import { useEffect, useState } from "react";

import { type FleetStats, api } from "../lib/api";

// Minimal in Epic 8 (fleet snapshot). Full fleet/agent/user tables land in Epic 10.
export function Admin() {
  const [fleet, setFleet] = useState<FleetStats | null>(null);

  useEffect(() => {
    api.fleetStats().then(setFleet).catch(() => setFleet(null));
  }, []);

  return (
    <>
      <div className="eyebrow">
        <span className="dot" aria-hidden="true" />
        Admin
      </div>
      <h1 style={{ fontSize: "clamp(2rem,5vw,3rem)" }}>Fleet overview</h1>
      <div className="grid cols-3" style={{ marginTop: "1.5rem" }}>
        <div className="card">
          <div className="lbl">Available slots</div>
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {fleet ? fleet.available : "—"}
          </div>
        </div>
        <div className="card">
          <div className="lbl">Total slots</div>
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {fleet ? fleet.total : "—"}
          </div>
        </div>
        <div className="card">
          <div className="lbl">In use</div>
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {fleet ? fleet.total - fleet.available : "—"}
          </div>
        </div>
      </div>
      <p className="subtle" style={{ marginTop: "1.5rem" }}>
        Per-VPS health, per-agent table and force actions arrive in Epic 10.
      </p>
    </>
  );
}
