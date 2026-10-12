// PHASE 4/5 glue: loads history from REST once, then keeps appending live WebSocket batches.
// Because history comes from the event store, a browser refresh does NOT lose the graphs.
import { useEffect, useRef, useState, useCallback } from "react";
import { get, WS } from "./api";

const fresh = (lastId = 0) => ({ run: null, meta: null, hosts: {}, feed: [], labels: [], tick: 0, ended: false, lastId });

function apply(s, evs) {
  for (const e of evs) {
    if (e.id <= s.lastId) continue;
    if (e.type === "run_start") {
      if (s.run !== e.run_id) Object.assign(s, fresh(e.id));
      s.run = e.run_id; s.meta = e.data;
    }
    s.lastId = e.id;
    if (e.run_id !== s.run) continue;
    s.tick = Math.max(s.tick, e.t);
    if (e.type === "flow_score") {
      const h = (s.hosts[e.host] ||= { points: [], latest: null });
      h.latest = { ...e.data, t: e.t };
      h.points.push({ t: e.t, trust: e.data.trust, anomaly: e.data.anomaly, state: e.data.state });
      if (h.points.length > 600) h.points.shift();
    } else if (e.type === "state_change" || e.type === "enforcement") {
      s.feed.unshift({ id: e.id, t: e.t, host: e.host, kind: e.type, ...e.data });
      if (s.feed.length > 300) s.feed.pop();
    } else if (e.type === "label") {
      s.labels.push({ host: e.host, ...e.data });
    } else if (e.type === "run_end") s.ended = true;
  }
}

export function useTrustFlow() {
  const S = useRef(fresh());
  const [, bump] = useState(0);
  const [connected, setConnected] = useState(false);
  const ingest = useCallback((evs) => { apply(S.current, evs); bump((n) => n + 1); }, []);

  useEffect(() => {
    let ws, retry, dead = false;
    const open = () => {
      ws = new WebSocket(WS);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (!dead) retry = setTimeout(boot, 1500); };
      ws.onmessage = (m) => ingest(JSON.parse(m.data).events);
    };
    const boot = () =>
      get("/api/runs/latest/events").then((evs) => { ingest(evs); open(); }).catch(() => { retry = setTimeout(boot, 1500); });
    boot();
    return () => { dead = true; clearTimeout(retry); ws && ws.close(); };
  }, [ingest]);

  return { ...S.current, connected, reset: () => { S.current = fresh(S.current.lastId); bump((n) => n + 1); } };
}
