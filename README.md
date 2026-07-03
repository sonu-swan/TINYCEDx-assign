# Tiny CEDX Agent Fleet

## 1. Industry & Scope
Industry: **general work-request processing** (generic ops/finance intake —
onboarding, renewal, review, report, intake categories, matching the seed
pack). Tier: baseline (5-stage governed pipeline, no domain-specific
extensions beyond what's specified). CASE_ID: `CEDX-XXXX` (placeholder;
replace with live-assigned id — see DECISIONS.md).

## 2. Agent topology
3 automated agents + 1 human role. Full contracts and diagram in
`ARCHITECTURE.md`. Roster (also in `out/audit.json` → `agents`):
- **Orchestrator** (`fleet/orchestrator.py`) — owns the run, no LLM calls, delegates only.
- **Worker** (`fleet/worker.py`) — drafts branded output, model-routed.
- **Verifier** (`fleet/verifier.py`) — independently checks/overrules Worker.
- **Operator** — human approver, tracked in `approval_trail`.

## 3. How to Run
```
make demo      # runs the fleet offline (REPLAY_LLM=true) on SEED_DIR
make verify    # runs the provided grading gate on out/audit.json
```
Or the single required command: `docker compose up` (runs `make demo && make verify`).
Real-LLM path: `REPLAY_LLM=false LLM_API_KEY=... LLM_MODEL=gpt-4o-mini make demo`.

## 4. Controls
| Probe | What it proves |
|---|---|
| `make probe-approval` | delivery refused without approval AND without CASE_ID amendment role sign-off on high-value records |
| `make probe-agent-failure` | Verifier catches hallucinated / malformed / abstained Worker output |
| `make probe-budget` | per-record cost ceiling raises `BUDGET_EXCEEDED`, never silent overspend |
| `make probe-append-only` | event log is append-only shaped; deletion is detectable |
| `make probe-idempotency` | two runs of `make demo` produce no duplicate records |

## 5. Planted-problem handling
Data layer: `fleet/detectors.py`. Agent layer: `fleet/verifier.py` +
`fleet/orchestrator.py` (step/cost ceiling). See table in `TASK.md` for the
full reason-code list; every one is exercised either in the dev-seed run
(`out/audit.json`) or a dedicated probe — see DECISIONS.md's honest note on
which is which.

**Records that reached delivery in the dev run:** REC-001..010, 017(v2),
018, 019, 020 — 15 total. **Exceptions:** REC-011 (STALE), 012
(MISSING_INPUT), 013 (OUTLIER), 014 (INJECTION_BLOCKED), 015 (LOW_CONFIDENCE),
021 (LOW_CONFIDENCE), 022 (INJECTION_BLOCKED). **Superseded:** REC-017 v1.

## 6. Generalization
No record ID or literal value is referenced anywhere in `fleet/detectors.py`
or `fleet/verifier.py`. Every threshold (outlier, injection pattern,
ambiguity pattern) is either computed from the batch or matched by pattern —
see DECISIONS.md for the specific reasoning per detector.

## 7. LLM/agent contract & eval
`REPLAY_LLM=true` (default): Worker's "model call" is deterministically
derived from the source record and committed to `/transcripts/<hash>.json`,
content-addressed so re-runs are byte-identical (see `fleet/transcripts.py`).
`REPLAY_LLM=false`: calls a real model via `LLM_API_KEY`/`LLM_MODEL` (see
`fleet/worker.py::_call_real_llm`). Eval harness: `make eval` — 11 golden
cases across Orchestrator/detector logic (7) and Verifier logic (4), rule-based
judging (see DECISIONS.md for why, given no live LLM in replay mode).

## 8. Cost & scale
See DECISIONS.md § "Router policy + cost numbers" for current run numbers
and the 10k/day projection.

## 9. Amendment
`AMENDMENT: role=<R> threshold=<T>` is printed at startup and recorded under
`amendment` in `out/audit.json`. Computed from `CASE_ID` per the formula in
`TASK.md` Step 8 (`fleet/approval.py::amendment_for`). Enforced (not just
logged) at the delivery gate in `fleet/approval.py::ApprovalTrail.try_deliver`.

## 10. AI usage / real-vs-faked
Built with AI assistance. Nothing is stubbed: intake actually parses JSON +
`.eml` + PDF text; detectors are rule-based against the full batch;
Worker/Verifier exchange typed objects, not strings; transcripts are
content-addressed and hash-verified by the provided `verify_audit.py` (not
modified). See DECISIONS.md for the one explicit limitation (no live LLM
judge in offline mode) stated plainly rather than hidden.

## 11. Tradeoffs & next week
Tradeoffs: sequential (not concurrent) record processing; rule-based eval
judge instead of a live LLM judge in replay mode; only one Worker model
family pair (cheap/strong) rather than a 3-tier router. Next week: add
concurrency with a global cost budget (not just per-record), add the 4th
agent this task's live-extension slot is clearly built for (a Redactor
stripping PII before delivery — the contract pattern already supports adding
it: new agent, `can_call: []`, wired into Orchestrator between Verifier-pass
and Delivery), and swap the rule-based eval judge for a real model-graded
judge on the `REPLAY_LLM=false` path.
