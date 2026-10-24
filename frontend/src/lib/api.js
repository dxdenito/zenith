const BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
export const wsUrl = (path) => BASE.replace(/^http/, "ws") + path;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function messageFrom(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (status === 422) return "Check your details and try again.";
  return "Something went wrong. Please try again.";
}

async function send(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection.", 0);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) throw new ApiError(messageFrom(data, res.status), res.status);
  return data;
}

let refreshing = null;

function refreshSession() {
  if (!refreshing) {
    refreshing = send("/auth/refresh", { method: "POST" }).finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

async function authed(path, options = {}) {
  try {
    return await send(path, options);
  } catch (err) {
    if (err.status !== 401) throw err;
    await refreshSession();
    return send(path, options);
  }
}

export const api = {
  register: (payload) => send("/auth/register", { method: "POST", body: payload }),
  login: (payload) => send("/auth/login", { method: "POST", body: payload }),
  logout: () => send("/auth/logout", { method: "POST" }),
  connectDeriv: () => authed("/accounts/deriv/connect", { method: "POST" }),
  accounts: () => authed("/accounts"),
  overview: () => authed("/accounts/overview"),
  symbols: () => authed("/markets/symbols"),
  ticks: (symbol, limit = 300) =>
    authed(`/markets/symbols/${encodeURIComponent(symbol)}/ticks?limit=${limit}`),
  setCollect: (symbol, collect) =>
    authed(`/markets/symbols/${encodeURIComponent(symbol)}`, {
      method: "PATCH",
      body: { collect },
    }),
  switchAccount: (account_id) =>
  authed("/accounts/active", { method: "POST", body: { account_id } }),
  me: () => authed("/auth/me"),
  authed,
};

