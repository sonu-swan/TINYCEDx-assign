import json, subprocess, sys, os

with open("out/audit.json") as f:
    r1 = json.load(f)

# re-run the pipeline
subprocess.run([sys.executable, "-m", "fleet.main"], check=True,
                env=os.environ | {"PYTHONPATH": "."})

with open("out/audit.json") as f:
    r2 = json.load(f)

ids1 = [(r["id"], r["version"], r["status"]) for r in r1.get("records", [])]
ids2 = [(r["id"], r["version"], r["status"]) for r in r2.get("records", [])]
if len(ids2) != len(set(ids2)):
    print(f"FAIL: duplicate record ids after 2nd run: {ids2}"); sys.exit(1)
if sorted(ids1) != sorted(ids2):
    print(f"FAIL: record set changed between runs (non-deterministic)"); sys.exit(1)
print(f"OK: {len(ids2)} records, no duplicates after 2nd run, same record set")
print("PASS: probe-idempotency")
sys.exit(0)
