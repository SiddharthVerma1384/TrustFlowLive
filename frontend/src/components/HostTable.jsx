import { COLORS } from "../api";

// Traffic view: the metadata features per host (never payload) with a trust bar.
export default function HostTable({ hosts, onPick, picked }) {
  const ids = Object.keys(hosts).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  return (
    <table className="tbl">
      <thead><tr><th>host</th><th>state</th><th>trust</th><th>pkt/s</th><th>size</th><th>dsts</th><th>ports</th><th>SYN</th><th>action</th></tr></thead>
      <tbody>
        {ids.map((id) => {
          const l = hosts[id].latest, f = l.features;
          return (
            <tr key={id} onClick={() => onPick(id)} className={picked === id ? "sel" : ""}>
              <td><b>{id}</b></td>
              <td><span className="dot" style={{ background: COLORS[l.state] }} />{l.state}</td>
              <td><div className="bar"><i style={{ width: `${l.trust * 100}%`, background: COLORS[l.state] }} /></div></td>
              <td>{f.pkt_rate.toFixed(0)}</td><td>{f.mean_size.toFixed(0)}</td><td>{f.unique_dsts.toFixed(1)}</td>
              <td>{f.unique_ports.toFixed(1)}</td><td>{f.syn_ratio.toFixed(2)}</td><td>{l.action}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
