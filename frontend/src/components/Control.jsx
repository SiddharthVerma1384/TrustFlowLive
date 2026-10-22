import { useEffect, useState } from "react";
import { get, post, del } from "../api";

// Experiment control: build a scenario (preset OR your own attacks) and run it from the browser.
export default function Control({ onReset }) {
  const [opts, setOpts] = useState({ scenarios: [], topologies: [], attacks: [] });
  const [loadError, setLoadError] = useState("");
  const [f, setF] = useState({ scenario: "mixed", topology: "star", hosts: 6, speed: 5, seed: 1, duration: 170 });
  const [custom, setCustom] = useState([]);
  const [a, setA] = useState({ attack: "port_scan", host: "h3", start: 20, end: 70 });
  const [mode, setMode] = useState("live");
  const [iface, setIface] = useState("any");
  const [message, setMessage] = useState("");
  useEffect(() => {
    get("/api/scenarios")
      .then(setOpts)
      .catch((err) => setLoadError(`Could not load control options: ${err.message}`));
  }, []);
  const num = (e) => (e.target.type === "number" ? +e.target.value : e.target.value);
  const set = (k) => (e) => setF({ ...f, [k]: num(e) });
  const setAtk = (k) => (e) => setA({ ...a, [k]: num(e) });
  const start = () => {
    setMessage("Starting WSL live pipeline…");
    const call = mode === "live"
      ? post("/api/live/start", { scenario: f.scenario, topology: f.topology, hosts: f.hosts, iface })
      : post("/api/runs", { ...f, custom: custom.length ? custom : null });
    call.then((r) => setMessage(`${mode === "live" ? "Live WSL" : "Simulator"} run started: ${r.run_id || "running"}`))
      .catch((err) => setMessage(`Could not start run: ${err.message}`));
  };
  const stop = () => (mode === "live" ? post("/api/live/stop") : post("/api/runs/stop"))
    .then(() => setMessage("Run stopped"))
    .catch((err) => setMessage(`Could not stop run: ${err.message}`));

  return (
    <div className="form">
      {loadError && <p className="note error">{loadError}</p>}
      <label>Run mode<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="live">Live WSL (Mininet/OVS/OS-Ken/TShark)</option><option value="simulator">Simulator</option></select></label>
      <label>Preset scenario<select value={f.scenario} onChange={set("scenario")} disabled={mode === "live" || custom.length > 0}>{opts.scenarios.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label>Topology<select value={f.topology} onChange={set("topology")}>{opts.topologies.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label>Hosts<input type="number" min="3" max="12" value={f.hosts} onChange={set("hosts")} /></label>
      {mode === "live" && <label>Capture interface<input value={iface} onChange={(e) => setIface(e.target.value)} placeholder="any" /></label>}
      <label>Ticks / second<input disabled={mode === "live"} type="number" min="1" max="50" value={f.speed} onChange={set("speed")} /></label>
      <label>Duration (ticks)<input disabled={mode === "live"} type="number" min="60" max="400" value={f.duration} onChange={set("duration")} /></label>
      <label>Seed<input disabled={mode === "live"} type="number" value={f.seed} onChange={set("seed")} /></label>

      <fieldset className="custom">
        <legend>Custom attacks (simulator mode only)</legend>
        <div className="row">
          <select disabled={mode === "live"} value={a.attack} onChange={setAtk("attack")}>{opts.attacks.map((x) => <option key={x}>{x}</option>)}</select>
          <input disabled={mode === "live"} aria-label="host" style={{ width: 70 }} value={a.host} onChange={setAtk("host")} />
          <input disabled={mode === "live"} aria-label="start tick" type="number" style={{ width: 80 }} value={a.start} onChange={setAtk("start")} />
          <input disabled={mode === "live"} aria-label="end tick" type="number" style={{ width: 80 }} value={a.end} onChange={setAtk("end")} />
          <button disabled={mode === "live"} onClick={() => setCustom([...custom, a])}>Add attack</button>
        </div>
        {custom.map((c, i) => (
          <div key={i} className="row"><code>{c.attack} on {c.host}, ticks {c.start}–{c.end} (after baseline)</code>
            <button onClick={() => setCustom(custom.filter((_, j) => j !== i))}>remove</button></div>
        ))}
      </fieldset>

      <div className="row">
        <button className="primary" onClick={start}>Start run</button>
        <button onClick={stop}>Stop</button>
        <button onClick={() => del("/api/events").then(onReset)}>Clear history</button>
      </div>
      {message && <p className="note">{message}</p>}
      <p className="note">Live WSL starts the real Mininet → OVS → OS-Ken → TShark pipeline. Simulator mode uses synthetic traffic without WSL.</p>
    </div>
  );
}
