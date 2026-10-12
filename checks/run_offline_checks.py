"""Runs steps 1-4 (no server needed).   Run: python -m checks.run_offline_checks"""
import importlib
for m in ("step1_store", "step2_engine", "step3_mapping", "step4_csv"):
    print("=" * 14, m, "=" * 14)
    importlib.import_module(f"checks.{m}")
print("\nALL OFFLINE CHECKS PASSED")
