import { useEffect, useState } from "react";
import { get, post, del } from "../api";

// Experiment control: build a scenario (preset OR your own attacks) and run it from the browser.
export default function Control({ onReset }) {
  const [opts, setOpts] = useState({ scenarios: [], topologies: [], attacks: [] });
  const [f, setF] = useState({ scenario: "mixed", topology: "star", hosts: 6, speed: 5, seed: 1, duration: 170 });
  const [custom, setCustom] = useState([]);
  const [a, setA] = useState({ attack: "port_scan", host: "h3", start: 20, end: 70 });
  useEffect(() => { get("/api/scenarios").then(setOpts); }, []);
  const num = (e) => (e.target.type === "number" ? +e.target.value : e.target.value);
  const set = (k) => (e) => setF({ ...f, [k]: num(e) });
  const setAtk = (k) => (e) => setA({ ...a, [k]: num(e) });
  const start = () => post("/api/runs", { ...f, custom: custom.length ? custom : null });

  return (
    <div className="form">
      <label>Preset scenario<select value={f.scenario} onChange={set("scenario")} disabled={custom.length > 0}>{opts.scenarios.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label>Topology<select value={f.topology} onChange={set("topology")}>{opts.topologies.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label>Hosts<input type="number" min="3" max="12" value={f.hosts} onChange={set("hosts")} /></label>
      <label>Ticks / second<input type="number" min="1" max="50" value={f.speed} onChange={set("speed")} /></label>
      <label>Duration (ticks)<input type="number" min="60" max="400" value={f.duration} onChange={set("duration")} /></label>
      <label>Seed<input type="number" value={f.seed} onChange={set("seed")} /></label>

      <fieldset className="custom">
        <legend>Custom attacks (overrides the preset when the list is not empty)</legend>
        <div className="row">
          <select value={a.attack} onChange={setAtk("attack")}>{opts.attacks.map((x) => <option key={x}>{x}</option>)}</select>
          <input aria-label="host" style={{ width: 70 }} value={a.host} onChange={setAtk("host")} />
          <input aria-label="start tick" type="number" style={{ width: 80 }} value={a.start} onChange={setAtk("start")} />
          <input aria-label="end tick" type="number" style={{ width: 80 }} value={a.end} onChange={setAtk("end")} />
          <button onClick={() => setCustom([...custom, a])}>Add attack</button>
        </div>
        {custom.map((c, i) => (
          <div key={i} className="row"><code>{c.attack} on {c.host}, ticks {c.start}–{c.end} (after baseline)</code>
            <button onClick={() => setCustom(custom.filter((_, j) => j !== i))}>remove</button></div>
        ))}
      </fieldset>

      <div className="row">
        <button className="primary" onClick={start}>Start run</button>
        <button onClick={() => post("/api/runs/stop")}>Stop</button>
        <button onClick={() => del("/api/events").then(onReset)}>Clear history</button>
      </div>
      <p className="note">Simulator mode drives the real TrustFlow engine with synthetic traffic. External data (CSV, your own scripts, real TShark) enters through the adapter and appears here with no change.</p>
    </div>
  );
}
