import sys
sys.path.insert(0, ".")
from fleet.models import RawRecord, WorkerOutput
from fleet.verifier import Verifier

v = Verifier()
source = RawRecord(id="REC-900", owner="a.shah", deadline="2026-07-15", category="ONBOARDING",
                    notes="clean record", version=1, amount=4800, source_format="feed",
                    source_version_hash="sha256:test")

# Case 1: hallucination — worker invents an amount not in the source
bad_draft = {"id": "REC-900", "owner": "a.shah", "category": "ONBOARDING",
             "amount": 999999, "deadline": "2026-07-15", "branded_summary": "fabricated"}
out = WorkerOutput("REC-900", bad_draft, "gpt-4o-mini", "worker-v1", 100, 50, 0.0001, 10, 0, "ok", "sha256:x")
verdict = v.check(source, out)
if verdict.verdict != "fail" or verdict.reason_code != "AGENT_HALLUCINATION":
    print(f"FAIL: hallucinated output not caught: {verdict}"); sys.exit(1)
print("OK: AGENT_HALLUCINATION caught by Verifier, never would reach delivery")

# Case 2: malformed — worker output missing required keys
malformed = {"id": "REC-900", "amount": 4800}
out2 = WorkerOutput("REC-900", malformed, "gpt-4o-mini", "worker-v1", 90, 40, 0.0001, 8, 0, "ok", "sha256:y")
verdict2 = v.check(source, out2)
if verdict2.verdict != "fail" or verdict2.reason_code != "AGENT_MALFORMED":
    print(f"FAIL: malformed output not caught: {verdict2}"); sys.exit(1)
print("OK: AGENT_MALFORMED caught by Verifier")

# Case 3: worker abstained (low confidence) -> routed to human, not delivered
out3 = WorkerOutput("REC-900", None, "gpt-4o-mini", "worker-v1", 50, 0, 0.0, 5, 0, "abstained", None,
                     abstain_reason="ambiguous source")
verdict3 = v.check(source, out3)
if verdict3.verdict not in ("needs_human", "fail"):
    print(f"FAIL: abstain not routed: {verdict3}"); sys.exit(1)
print("OK: abstained worker output routed to human")

print("PASS: probe-agent-failure")
sys.exit(0)
