import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { get } from "../api";

// PHASE 10 view: reads evaluation/results/*.json written by `python -m evaluation.experiments`.
const Table = ({ rows }) => (
  <table className="tbl"><thead><tr>{Object.keys(rows[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody></table>
);

export default function Research() {
  const [r, setR] = useState(null);
  useEffect(() => { get("/api/research").then(setR); }, []);
  if (!r) return <div className="empty">Loading…</div>;
  if (!Object.keys(r).length) return <div className="empty">No results yet. Run <code>python -m evaluation.experiments</code>.</div>;
  return (
    <div className="grid2">
      {r.ablation && <section><h4>Feature ablation (F1 when one feature is removed)</h4><Table rows={r.ablation} /></section>}
      {r.hysteresis && <section><h4>Policy hysteresis (state flips vs F1)</h4><Table rows={r.hysteresis} /></section>}
      {r.scalability && <section><h4>Scalability (µs per scored window)</h4>
        <ResponsiveContainer width="100%" height={200}><LineChart data={r.scalability}><CartesianGrid stroke="#e3e8ee" />
          <XAxis dataKey="hosts" scale="log" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11 }} /><YAxis domain={[0, "auto"]} tick={{ fontSize: 11 }} /><Tooltip />
          <Line dataKey="us_per_window" stroke="#1f3a8a" strokeWidth={2.5} isAnimationActive={false} /></LineChart></ResponsiveContainer></section>}
      {r.multi_seed && <section><h4>Mean ± std over 5 seeds</h4>
        <Table rows={Object.entries(r.multi_seed.overall).map(([k, v]) => ({ metric: k, mean: v.mean, std: v.std }))} />
        <Table rows={Object.entries(r.multi_seed.recall_by_attack).map(([k, v]) => ({ attack: k, recall: v.mean, std: v.std }))} /></section>}
      {r.formula && <section style={{ gridColumn: "1 / -1" }}><h4>Formula sweep (z_floor × beta_up)</h4><Table rows={r.formula} /></section>}
    </div>
  );
}
