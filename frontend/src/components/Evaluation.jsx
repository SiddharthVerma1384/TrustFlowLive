import { useEffect, useState } from "react";
import { get } from "../api";

// PHASE 9 view: confusion matrix, P/R/F1, per-attack recall, detection delay, FP/FN lists.
export default function Evaluation({ run, ended }) {
  const [ev, setEv] = useState(null);
  const [minState, setMin] = useState("Restricted");
  const load = () => run && get(`/api/runs/${run}/evaluation?min_state=${minState}`).then(setEv);
  useEffect(() => { load(); }, [run, ended, minState]);
  if (!run) return <div className="empty">Run a scenario first.</div>;
  if (!ev) return <div className="empty">Loading…</div>;
  const c = ev.confusion;
  return (
    <div className="grid2">
      <div>
        <div className="row">
          <label>Flag as anomalous when state ≥ <select value={minState} onChange={(e) => setMin(e.target.value)}>
            {["Monitored", "Restricted", "Quarantine", "Blocked"].map((s) => <option key={s}>{s}</option>)}</select></label>
          <button onClick={load}>Refresh</button>
        </div>
        <div className="kpis">
          {[["Precision", ev.precision], ["Recall", ev.recall], ["F1", ev.f1], ["FP rate", ev.fpr]].map(([k, v]) =>
            <div key={k}><span>{k}</span><b>{v.toFixed(3)}</b></div>)}
        </div>
        <table className="tbl cm"><thead><tr><th></th><th>flagged</th><th>not flagged</th></tr></thead><tbody>
          <tr><th>attack (truth)</th><td className="ok">TP {c.tp}</td><td className="bad">FN {c.fn}</td></tr>
          <tr><th>benign (truth)</th><td className="bad">FP {c.fp}</td><td className="ok">TN {c.tn}</td></tr>
        </tbody></table>
      </div>
      <div>
        <h4>Recall per attack</h4>
        {Object.entries(ev.per_attack).map(([a, v]) => (
          <div key={a} className="rowbar"><span>{a}</span><div className="bar"><i style={{ width: `${v.recall * 100}%`, background: v.recall > 0.5 ? "#2f9e62" : "#d23b3b" }} /></div><em>{v.recall.toFixed(2)}</em></div>
        ))}
        <h4>Detection delay (ticks after attack start)</h4>
        <table className="tbl"><tbody>{Object.entries(ev.detection_delay_ticks).map(([k, v]) =>
          <tr key={k}><td>{k}</td><td>{v === null ? <span className="bad">never detected</span> : v}</td></tr>)}</tbody></table>
        <p className="note">{ev.false_positives.length} false-positive and {ev.false_negatives.length} false-negative windows listed (first 50 each). Recovery-lag windows count as FP.</p>
      </div>
    </div>
  );
}
