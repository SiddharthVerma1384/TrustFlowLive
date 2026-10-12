import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ReferenceArea, ResponsiveContainer, CartesianGrid } from "recharts";
import { COLORS } from "../api";

// Trust-over-time with state thresholds, ground-truth attack bands and hysteresis visible as slow recovery.
export default function TrustChart({ host, hosts, labels }) {
  const h = hosts[host];
  if (!h) return <div className="empty">Pick a host.</div>;
  const bands = labels.filter((l) => l.host === host);
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={h.points} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid stroke="#e3e8ee" />
        {bands.map((b, i) => <ReferenceArea key={i} x1={b.t_start} x2={b.t_end} fill="#d23b3b" fillOpacity={0.09} label={{ value: b.attack, fontSize: 11, fill: "#d23b3b", position: "insideTopLeft" }} />)}
        {[["Trusted", 0.8], ["Monitored", 0.6], ["Restricted", 0.4], ["Quarantine", 0.2]].map(([n, y]) => (
          <ReferenceLine key={n} y={y} stroke={COLORS[n]} strokeDasharray="4 4" />
        ))}
        <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(3) : v)} />
        <Line type="monotone" dataKey="trust" stroke="#1f3a8a" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="anomaly" stroke="#9aa6b5" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
