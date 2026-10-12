import { COLORS } from "../api";

// Terminal-style log: ties the browser back to what the controller is doing.
export default function Feed({ feed }) {
  if (!feed.length) return <div className="empty">No state changes yet.</div>;
  return (
    <div className="feed">
      {feed.map((e) => e.kind === "state_change" ? (
        <div key={e.id}><span className="t">t={String(e.t).padStart(3, "0")}</span> <b>{e.host}</b>{" "}
          <span style={{ color: COLORS[e.from] }}>{e.from}</span> → <span style={{ color: COLORS[e.to] }}>{e.to}</span> (trust {e.trust.toFixed(2)})</div>
      ) : (
        <div key={e.id} className="rule"><span className="t">t={String(e.t).padStart(3, "0")}</span> OpenFlow&nbsp;{e.host}: {e.action} <code>{e.rule}</code></div>
      ))}
    </div>
  );
}
