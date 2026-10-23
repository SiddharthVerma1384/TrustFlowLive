// All HTTP/WS addresses live here. Change the environment value if the backend moves.
// Use the IPv4 loopback explicitly for local development: on some machines
// localhost resolves to another service listening on IPv6 ::1.
export const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
export const WS = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000/ws";
const json = async (r) => {
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `API request failed (${r.status})`);
  return data;
};
export const get = (p) => fetch(API + p).then(json);
export const post = (p, body) =>
  fetch(API + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(json);
export const del = (p) => fetch(API + p, { method: "DELETE" }).then(json);

export const STATES = ["Trusted", "Monitored", "Restricted", "Quarantine", "Blocked"];
export const COLORS = { Trusted: "#2f9e62", Monitored: "#d9a21b", Restricted: "#e8742c", Quarantine: "#d23b3b", Blocked: "#7a1530" };
