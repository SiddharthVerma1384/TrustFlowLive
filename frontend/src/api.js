// All HTTP/WS addresses live here. Change API once if the backend moves.
export const API = "http://localhost:8000";
export const WS = "ws://localhost:8000/ws";
export const get = (p) => fetch(API + p).then((r) => r.json());
export const post = (p, body) =>
  fetch(API + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then((r) => r.json());
export const del = (p) => fetch(API + p, { method: "DELETE" }).then((r) => r.json());

export const STATES = ["Trusted", "Monitored", "Restricted", "Quarantine", "Blocked"];
export const COLORS = { Trusted: "#2f9e62", Monitored: "#d9a21b", Restricted: "#e8742c", Quarantine: "#d23b3b", Blocked: "#7a1530" };
