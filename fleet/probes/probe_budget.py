import os, sys
sys.path.insert(0, ".")
# Force an impossibly low ceiling so ANY real record trips it deterministically.
os.environ["MAX_COST_USD_PER_RECORD"] = "0.0000001"
os.environ["MAX_STEPS_PER_RECORD"] = "4"

from fleet.models import RawRecord
from fleet.orchestrator import Orchestrator

orch = Orchestrator(replay=True, case_id="CEDX-TEST", transcripts_dir="out/_probe_transcripts")
record = RawRecord(id="REC-901", owner="a.shah", deadline="2026-07-15", category="ONBOARDING",
                    notes="clean record", version=1, amount=4800, source_format="feed",
                    source_version_hash="sha256:test")

result = orch.process_record(record)
if result["status"] == "delivered":
    print(f"FAIL: record delivered despite budget ceiling: {result}"); sys.exit(1)
if result["reason_code"] != "BUDGET_EXCEEDED":
    print(f"FAIL: expected BUDGET_EXCEEDED, got {result['reason_code']}"); sys.exit(1)
print("OK: over-ceiling record raised BUDGET_EXCEEDED and was routed, not delivered")
print("PASS: probe-budget")
sys.exit(0)
