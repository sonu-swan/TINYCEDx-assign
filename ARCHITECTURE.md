# Architecture — Tiny CEDX Agent Fleet

## Agent roster

| Agent | Role | Models | can_call | File |
|---|---|---|---|---|
| Orchestrator | orchestrator | — (no LLM calls) | worker, verifier, operator | `fleet/orchestrator.py` |
| Worker | worker | gpt-4o-mini (default), claude-3-5-haiku (escalated) | — | `fleet/worker.py` |
| Verifier | verifier | gpt-4o-mini | — | `fleet/verifier.py` |
| Operator | operator | — (human) | — | represented in `approval_trail`, not a code file |

## Topology (per record)

```
Intake (fleet/intake.py)
   │  persists RawRecord (typed contract, models.py)
   ▼
Orchestrator (fleet/orchestrator.py)
   │  runs detectors.classify_batch() — RULE-BASED, no LLM call
   │  Class-A hit? ──────────────────────► exception_queue, STOP
   │  clean/Class-B?
   ▼
Worker.draft(record)              [Assembly]
   │  model router picks cheap/strong model (fleet/router.py)
   │  returns WorkerOutput (typed contract)
   ▼
Verifier.check(record, WorkerOutput)   [Review — agent-checks-agent]
   │  independently RE-DERIVES expected fields from the SOURCE record
   │  (never trusts Worker's self-report) → VerifierVerdict
   │  verdict=fail? ─► retry Worker once (escalated model) ─► still fail? exception_queue, STOP
   ▼
verdict=pass
   ▼
ApprovalTrail (fleet/approval.py)      [Review — approval chain]
   │  draft → in_review → approved (operator)
   │  amount >= CASE_ID threshold T?  → requires SECOND approval by role R
   │  try_deliver() refused server-side unless both gates cleared
   ▼
Delivery: branded_package.json + audit.json record  [Delivery]
```

## Where the Verifier overrules the Worker

`fleet/verifier.py::Verifier.check()` — the Worker can report `status="ok"`
and still get `verdict="fail"` from the Verifier if the draft's `amount`,
`owner`, `category`, or `id` don't match what the Verifier independently
recomputes from the source record. That divergence is `AGENT_HALLUCINATION`.
Missing required keys is `AGENT_MALFORMED`. Both are logged in the same
`agent_trace` span list as the Worker's own span — both sides of the
disagreement are visible in one place (`out/audit.json` → `records[].agent_trace`).

## Where budget/router decisions live

- Router policy (cheap-vs-strong model selection): `fleet/router.py::pick_model()`.
- Per-record step/cost ceiling enforcement: `fleet/orchestrator.py::process_record()`,
  checked after every Worker call, before the record is allowed to proceed.

## Why 3+ separate agents instead of one function

The Worker and Verifier have **different objectives**, not just different
code paths. The Worker's objective is "produce a plausible answer." The
Verifier's objective is "find a reason this answer is wrong." An agent
checking its own output shares its own blind spots and reasoning path — it
tends to confirm the same mistake it just made. A second agent with an
adversarial objective, working only from the source record (not the Worker's
reasoning), catches classes of error the first agent structurally cannot see
in itself. This is the same principle behind independent code review and
segregation of duties in financial controls — the CASE_ID amendment's
second-approver requirement is the same principle applied to human review.
