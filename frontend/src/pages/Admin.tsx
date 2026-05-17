import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { StatusBadge } from "../components/bits";

type Overview = Awaited<ReturnType<typeof api.admin.overview>>;
type AdminAgent = Awaited<ReturnType<typeof api.admin.agents>>[number];
type AdminUser = Awaited<ReturnType<typeof api.admin.users>>[number];

export function Admin() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [agents, setAgents] = useState<AdminAgent[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [o, a, u] = await Promise.all([
      api.admin.overview(),
      api.admin.agents(),
      api.admin.users(),
    ]);
    setOv(o);
    setAgents(a);
    setUsers(u);
  }, []);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const act = async (id: string, action: string) => {
    setBusy(id + action);
    try {
      await api.admin.action(id, action);
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const s = ov?.slots;
  const cards: [string, number | undefined][] = [
    ["Total slots", s?.total],
    ["Available", s?.available],
    ["Assigned", s?.assigned],
    ["Error", s?.error],
    ["Users", ov?.users],
    ["Agents", ov?.agents],
  ];

  return (
    <>
      <div className="eyebrow">
        <span className="dot" aria-hidden="true" />
        Admin
      </div>
      <h1 style={{ fontSize: "clamp(2rem,5vw,3rem)" }}>Fleet control</h1>

      <div className="grid cols-3" style={{ margin: "1.5rem 0 2.5rem" }}>
        {cards.map(([label, val]) => (
          <div className="card" key={label}>
            <div className="lbl">{label}</div>
            <div style={{ fontSize: "2rem", fontWeight: 700 }}>{val ?? "—"}</div>
          </div>
        ))}
      </div>

      <h2 style={{ fontSize: "1.4rem" }}>Agents</h2>
      <div className="card" style={{ overflowX: "auto", marginBottom: "2.5rem" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Name</th>
              <th>Owner</th>
              <th>Slot</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.id}>
                <td>{a.display_name}</td>
                <td className="subtle">{a.owner}</td>
                <td className="subtle">{a.slot_name ?? "—"}</td>
                <td>
                  <StatusBadge status={a.status} />
                </td>
                <td>
                  <div className="row" style={{ gap: "0.4rem", flexWrap: "wrap" }}>
                    {["stop", "start", "restart", "wipe", "recycle"].map((x) => (
                      <button
                        key={x}
                        className={`btn btn-sm ${x === "recycle" ? "btn-danger" : "btn-ghost"}`}
                        disabled={busy === a.id + x}
                        onClick={() => act(a.id, x)}
                      >
                        {x}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {agents.length === 0 && (
              <tr>
                <td colSpan={5} className="subtle">
                  No agents.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontSize: "1.4rem" }}>Users</h2>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Email</th>
              <th>Username</th>
              <th>Admin</th>
              <th>Agents</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td className="subtle">{u.username}</td>
                <td>{u.is_admin ? "yes" : "—"}</td>
                <td>{u.agents}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
