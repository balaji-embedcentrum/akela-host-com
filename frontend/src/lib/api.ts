// Typed API client. Same-origin; the Vite dev server proxies /api → backend so
// the HttpOnly session cookie is sent automatically.

export interface User {
  id: string;
  email: string;
  username: string;
  provider: string;
  is_admin: boolean;
}

export interface Agent {
  id: string;
  display_name: string;
  status: string;
  slot_name: string | null;
  a2a_url: string | null;
  workspace_url: string | null;
  monthly_cost_cents: number;
  renewal_date: string | null;
  api_key: string | null;
}

export interface FleetStats {
  available: number;
  total: number;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* non-JSON */
    }
    throw new ApiError(r.status, detail);
  }
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T);
}

export const api = {
  loginUrl: (provider: string, redirect = "/dashboard") =>
    `/api/auth/login?provider=${provider}&redirect=${encodeURIComponent(redirect)}`,
  me: () => req<User>("/api/auth/me"),
  logout: () => req<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  fleetStats: () => req<FleetStats>("/api/fleet/stats"),

  listAgents: () => req<Agent[]>("/api/agents"),
  getAgent: (id: string) => req<Agent>(`/api/agents/${id}`),
  checkout: (display_name: string) =>
    req<{ agent_id: string; checkout_url: string }>("/api/agents/checkout", {
      method: "POST",
      body: JSON.stringify({ display_name }),
    }),
  rename: (id: string, display_name: string) =>
    req<Agent>(`/api/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ display_name }),
    }),
  stop: (id: string) => req<Agent>(`/api/agents/${id}/stop`, { method: "POST" }),
  start: (id: string) => req<Agent>(`/api/agents/${id}/start`, { method: "POST" }),
  redeploy: (id: string, env: Record<string, string>) =>
    req<Agent>(`/api/agents/${id}/redeploy`, {
      method: "POST",
      body: JSON.stringify({ env }),
    }),
  cancel: (id: string) => req<Agent>(`/api/agents/${id}/cancel`, { method: "POST" }),
};

export { ApiError };
