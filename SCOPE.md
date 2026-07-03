# SCOPE — push this during the live call (tracer checkpoint)

- **Candidate name:** (fill in)
- **CASE_ID (assigned live):** CEDX-XXXX  (placeholder — replace with your real live-assigned id)
- **Industry chosen:** general work-request processing (ops/finance intake)
- **Tier:** baseline
- **Stack / language:** Python 3.11, stdlib + jsonschema + pypdf

## Amendment (computed from CASE_ID at runtime — see fleet/approval.py)
```
H = sha256(CASE_ID)
role R      = ["risk_officer","legal_counsel","compliance","finance_controller"][ int(H[0],16) % 4 ]
threshold T = 10000 + (int(H[1:3],16) % 50) * 1000
```
- **My role R (for CEDX-XXXX):** legal_counsel
- **My threshold T (for CEDX-XXXX):** 30000
> Recomputes automatically once the real CASE_ID is set — nothing hardcoded.

## What I will build (the 5 governed stages)
- [x] Sources/Intake (parse feed.json + inbox PDF/email)
- [x] Orchestration (declarative normalize + exception queue, all reason codes)
- [x] Assembly (structured output + abstain path, model router)
- [x] Review (operator surface + approval state machine + CASE_ID amendment)
- [x] Delivery (branded package + append-only audit + replay)

## What I will deliberately NOT build (and why)
- A live LLM-graded eval judge in REPLAY_LLM=true mode — no model to call
  offline; the harness is rule-based instead and documented as such in
  DECISIONS.md, with a stub for the real path.
- Concurrent/batched record processing — sequential is correct for this
  scale; noted as the first thing that breaks at 10k records/day.
