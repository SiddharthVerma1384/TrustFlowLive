import { useState } from "react";
import { useTrustFlow } from "./useTrustFlow";
import { STATES, COLORS } from "./api";
import Topology from "./components/Topology";
import HostTable from "./components/HostTable";
import TrustChart from "./components/TrustChart";
import Feed from "./components/Feed";
import Evaluation from "./components/Evaluation";
import Research from "./components/Research";
import Control from "./components/Control";

const TABS = ["Live network", "Trust timeline", "Event feed", "Evaluation", "Research", "Control"];

export default function App() {
  const tf = useTrustFlow();
  const [tab, setTab] = useState(TABS[0]);
  const [picked, setPicked] = useState("h3");
  const ids = Object.keys(tf.hosts);
  const host = tf.hosts[picked] ? picked : ids[0];
  const counts = STATES.map((s) => [s, ids.filter((i) => tf.hosts[i].latest.state === s).length]);
  const learning = ids.length && ids.every((i) => tf.hosts[i].latest.phase === "learning");

  return (
    <div className="app">
      <header>
        <div><h1>TrustFlow</h1><span className="sub">metadata-only continuous zero-trust segmentation</span></div>
        <div className="status">
          <span className={tf.connected ? "live" : "off"}>{tf.connected ? "live" : "offline"}</span>
          {tf.run && <span>run {tf.run} · {tf.meta.scenario} · {tf.meta.topology} · t={tf.tick}{tf.ended ? " · finished" : ""}</span>}
          {tf.run && tf.meta.inputs && <span>hosts={tf.meta.inputs.hosts} · duration={tf.meta.inputs.duration} · iface={tf.meta.inputs.interface}</span>}
          {learning ? <span className="learn">learning baseline…</span> : null}
        </div>
      </header>
      <nav>{TABS.map((t) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}</nav>
      <div className="summary">
        {counts.map(([s, n]) => <div key={s}><i style={{ background: COLORS[s] }} />{s}<b>{n}</b></div>)}
        <div className="priv"><i style={{ background: "#1f3a8a" }} />payload bytes inspected<b>0</b></div>
      </div>
      <main>
        {tab === "Live network" && (<>
          <section className="card"><Topology meta={tf.meta} hosts={tf.hosts} labels={tf.labels} tick={tf.tick} /></section>
          <section className="card"><HostTable hosts={tf.hosts} onPick={(h) => { setPicked(h); }} picked={host} /></section>
        </>)}
        {tab === "Trust timeline" && (
          <section className="card">
            <div className="chips">{ids.map((i) => <button key={i} className={i === host ? "on" : ""} onClick={() => setPicked(i)}>{i}</button>)}</div>
            <TrustChart host={host} hosts={tf.hosts} labels={tf.labels} />
            <p className="note">Blue = trust, grey = anomaly, dashed lines = state thresholds, red band = ground-truth attack. Trust falls fast and recovers slowly; hysteresis delays upward state changes.</p>
          </section>
        )}
        {tab === "Event feed" && <section className="card"><Feed feed={tf.feed} /></section>}
        {tab === "Evaluation" && <section className="card"><Evaluation run={tf.run} ended={tf.ended} /></section>}
        {tab === "Research" && <section className="card"><Research /></section>}
        {tab === "Control" && <section className="card"><Control onReset={tf.reset} /></section>}
      </main>
    </div>
  );
}
