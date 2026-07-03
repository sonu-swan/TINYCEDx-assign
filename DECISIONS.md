# Decisions

## What I did NOT automate, and why
- **Final approval is a human action** (`approval_trail` actor `operator:reviewer`),
  not an LLM call. The task requires delivery to be refused server-side without
  sign-off — automating that away would defeat the control it's testing.
- **The amendment second-approver** (role R, threshold T) is likewise a human
  role, not simulated by an agent — a maker-checker control only means
  something if the checker isn't the same system as the maker.

## Outlier / abstain thresholds, and why they generalize
- **OUTLIER**: median absolute deviation (MAD), modified z-score `0.6745*(x-median)/MAD`,
  flagged at `|z| > 5`. MAD is robust to the outlier itself skewing the
  estimate (unlike mean+stdev, which the outlier drags toward itself). The
  threshold is computed FROM the batch every run — no literal dollar amount
  is hardcoded, so it holds on the held-out seed's different magnitudes.
- **LOW_CONFIDENCE**: category `"?"` or ambiguity language in `notes`
  (`unclear`, `inconsistent`, `could be`, ...). Pattern-based, not id-based.
- **INJECTION_BLOCKED**: regex patterns matching imperative override language
  (`ignore ... instructions`, `skip review`, `approve immediately`, `the real
  ... is`, `output approved`) rather than a literal string list — catches
  paraphrases of the same attack, not just the exact seed wording.

## Router policy + cost numbers
Default model: `gpt-4o-mini`. Escalate to `claude-3-5-haiku` when (a) this is
a retry after a Verifier rejection, or (b) `notes` exceeds 80 characters (a
proxy for records needing more careful reading). Both signals are computed
from the record, not from any id, so the policy holds on unseen data.

Current dev-seed run (`out/audit.json`): total cost **$0.000457** across 15
delivered + 7 exception records (22 processed + 1 superseded).
Avg/record ≈ **$0.00002**. Projected at 10,000 records/day ≈ **$0.2** if the
mix and pricing stay comparable — the real constraint at scale is LLM
provider rate limits and Verifier retry volume, not raw $/token.

## How provenance survives re-run
Every delivered record's `delivered_fields_hash` is checked against a
committed `/transcripts/<hash>.json` file at verify time
(`verify_audit.py` checks #8/#14). Transcripts are content-addressed
(filename = hash of the response), so re-running with the same source data
regenerates byte-identical transcripts — `make probe-idempotency` confirms
no duplicate records appear across two runs of `make demo`.

## What breaks first at 10,000 records
1. **Verifier retry volume** — if the held-out set's failure-injection rate
   holds, retries alone could double LLM call volume; the router's escalation
   trigger on retry compounds cost per failed record.
2. **Sequential processing** — the current orchestrator processes records
   one at a time; at 10k/day this needs batching/concurrency with a
   per-worker cost ceiling, not just a per-record one.
3. **Human approval throughput** — the approval chain assumes a human in the
   loop for every delivered record; at scale this needs tiered
   auto-approval for low-risk records with human review reserved for
   amendment-threshold and Verifier-flagged cases.

## CASE_ID
`CEDX-XXXX` placeholder used for local dev (matches `docker-compose.yml`
default). Recomputes `role`/`threshold` automatically from whatever
`CASE_ID` is set at runtime — nothing about the amendment is hardcoded to
this placeholder. Replace with the live-assigned CASE_ID before final commit.

## Honest note on the agent-layer failure demo
The `/seed` pack we received contains all documented **data-layer** planted
problems (STALE, MISSING_INPUT, OUTLIER, INJECTION_BLOCKED, LOW_CONFIDENCE,
SCHEMA_DRIFT, SUPERSEDED_VERSION) — verified by inspecting every record. It
does not contain a pre-built **agent-layer** failure (hallucination/loop/
malformed/budget), because those are properties of a model's *response* at
run time, not something encodable as static input data. We demonstrate the
Verifier's agent-checks-agent catch via `make probe-agent-failure` (feeds a
deliberately hallucinated/malformed Worker output directly to the Verifier)
and `make probe-budget` (forces the cost ceiling and confirms
`BUDGET_EXCEEDED` fires and routes, never silently overspending) — exactly
per the Makefile's own stated contract for those two targets.

## AI usage
Built with AI assistance end-to-end (per the task's explicit allowance). The
architecture decisions above — why 3 separate agents, MAD over hardcoded
thresholds, content-addressed transcripts for provenance, router escalation
signals — are the parts a reviewer should probe on the live call; the code
implementing them is straightforward once the design is fixed.
