"""STEP 3 - mapping: does YOUR field naming translate?   Run: python -m checks.step3_mapping
Edit MY_ROW below to match the column names your data uses, then run it."""
from adapter.mapping import to_features

MY_ROW = {"pps": 50, "avg_pkt_len": 600, "dst_count": 3, "port_count": 4, "syn_pct": 5}   # <- your names

f = to_features(MY_ROW)
print("translated to engine features:", f)
assert abs(f["syn_ratio"] - 0.05) < 1e-9, "syn_pct should become 0.05"
try:
    to_features({"pps": 1})
    raise SystemExit("FAIL: missing fields were accepted")
except ValueError as e:
    print("missing-field error works ->", str(e)[:80])
print("PASS step 3: mapping works. If your real names fail, add them to FIELD_MAP in adapter/mapping.py")
