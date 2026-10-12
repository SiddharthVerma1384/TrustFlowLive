"""
THE PLACE TO EDIT WHEN YOUR INPUT CHANGES.

TrustFlow's engine needs exactly these 5 numbers per host per time window:
    pkt_rate      packets per second sent by the host
    mean_size     average packet length (bytes)
    unique_dsts   distinct destination IPs contacted in the window
    unique_ports  distinct destination ports contacted
    syn_ratio     fraction of packets that are TCP SYN (0..1)

Whatever your source calls them (TShark, a CSV, a teammate's script, a dataset), list the
source's field name on the left and the TrustFlow feature (+ optional scale) on the right.
To ADD a new behavioural feature: add it to engine/core.py FEATURES, then map it here.
"""
from engine.core import FEATURES

# source field name  ->  (trustflow feature, multiplier)
FIELD_MAP = {
    # our own names
    **{f: (f, 1.0) for f in FEATURES},
    # common alternatives - add yours below
    "packets_per_sec": ("pkt_rate", 1.0),
    "pps": ("pkt_rate", 1.0),
    "avg_pkt_len": ("mean_size", 1.0),
    "avg_packet_size": ("mean_size", 1.0),
    "dst_ips": ("unique_dsts", 1.0),
    "dst_count": ("unique_dsts", 1.0),
    "dst_ports": ("unique_ports", 1.0),
    "port_count": ("unique_ports", 1.0),
    "syn_pct": ("syn_ratio", 0.01),       # source gives percent -> convert to ratio
    "syn_fraction": ("syn_ratio", 1.0),
}


def to_features(raw):
    """Translate a source's dict into the 5 engine features. Raises if any are missing."""
    out = {}
    for k, v in raw.items():
        if k in FIELD_MAP and v not in (None, ""):
            name, scale = FIELD_MAP[k]
            out[name] = float(v) * scale
    missing = [f for f in FEATURES if f not in out]
    if missing:
        raise ValueError(f"missing features {missing}; add a mapping for them in adapter/mapping.py")
    return out
