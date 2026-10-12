import { COLORS } from "../api";

// Draws the topology from the run_start event. Node colour = current trust state.
export default function Topology({ meta, hosts, labels, tick }) {
  if (!meta) return <div className="empty">No run yet. Open the Control tab and press Start run.</div>;
  const W = 680, H = 320;
  const sw = meta.nodes.filter((n) => n.kind === "switch");
  const hs = meta.nodes.filter((n) => n.kind === "host");
  const pos = {};
  sw.forEach((n, i) => (pos[n.id] = [((i + 1) * W) / (sw.length + 1), 80]));
  hs.forEach((n, i) => (pos[n.id] = [((i + 1) * W) / (hs.length + 1), 240]));
  const attack = (h) => labels.find((l) => l.host === h && l.t_start <= tick && tick < l.t_end)?.attack;
  const col = (h) => COLORS[hosts[h]?.latest?.state || "Trusted"];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="topo" role="img" aria-label="Network topology coloured by trust state">
      {meta.links.map(([a, b], i) => {
        const bad = hosts[b]?.latest && ["Quarantine", "Blocked"].includes(hosts[b].latest.state);
        return <line key={i} x1={pos[a][0]} y1={pos[a][1]} x2={pos[b][0]} y2={pos[b][1]}
          stroke={b in hosts ? col(b) : "#9aa6b5"} strokeWidth={bad ? 2 : 3} strokeDasharray={bad ? "6 5" : ""} opacity=".8" />;
      })}
      {sw.map((n) => (
        <g key={n.id} transform={`translate(${pos[n.id][0] - 26},${pos[n.id][1] - 16})`}>
          <rect width="52" height="32" rx="4" fill="#16202e" /><text x="26" y="21" textAnchor="middle" fill="#fff" fontSize="13">{n.id}</text>
        </g>
      ))}
      {hs.map((n) => {
        const l = hosts[n.id]?.latest, a = attack(n.id);
        return (
          <g key={n.id} transform={`translate(${pos[n.id][0]},${pos[n.id][1]})`}>
            <circle r="24" fill={col(n.id)} stroke="#16202e" strokeWidth="2" />
            <text y="5" textAnchor="middle" fill="#fff" fontSize="14" fontWeight="600">{n.id}</text>
            <text y="46" textAnchor="middle" fontSize="12" fill="#16202e">{l ? l.state : "learning"}</text>
            <text y="61" textAnchor="middle" fontSize="11" fill="#5b6878">{l ? `trust ${l.trust.toFixed(2)}` : ""}</text>
            {a && <g transform="translate(0,-38)"><rect x="-34" y="-11" width="68" height="18" rx="9" fill="#fff" stroke="#d23b3b" /><text y="2" textAnchor="middle" fontSize="10" fill="#d23b3b">{a}</text></g>}
          </g>
        );
      })}
    </svg>
  );
}
