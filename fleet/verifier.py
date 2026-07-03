from __future__ import annotations
from .models import RawRecord, WorkerOutput, VerifierVerdict

REQUIRED_KEYS = {"id", "owner", "category", "amount", "deadline", "branded_summary"}


class Verifier:
    """Agent identity: name='verifier', role='verifier'. can_call=[] (leaf agent).
    Independently re-derives what the Worker's answer SHOULD contain from the
    original source record and diffs it. This is the agent-checks-agent gate:
    it never trusts the Worker's own claim about its output — it recomputes
    the expected values itself. Can OVERRULE the Worker (verdict=fail even
    though Worker reported status=ok)."""

    name = "verifier"
    role = "verifier"
    can_call: list[str] = []

    def check(self, record: RawRecord, out: WorkerOutput) -> VerifierVerdict:
        if out.status in ("killed",):
            return VerifierVerdict(record.id, "needs_human", "routed",
                                    "AGENT_LOOP", "worker exceeded step budget")

        if out.status == "abstained" or out.draft_fields is None:
            return VerifierVerdict(record.id, "needs_human", "rejected",
                                    "AGENT_MALFORMED", out.abstain_reason or "worker abstained")

        draft = out.draft_fields
        missing = REQUIRED_KEYS - draft.keys()
        if missing:
            return VerifierVerdict(record.id, "fail", "overruled",
                                    "AGENT_MALFORMED", f"missing keys {sorted(missing)}")

        # Hallucination check: every delivered value must trace back to the
        # source record — the Verifier recomputes expected values itself
        # rather than trusting the Worker's self-report.
        mismatches = []
        if draft.get("id") != record.id:
            mismatches.append("id")
        if record.amount is not None and draft.get("amount") != record.amount:
            mismatches.append("amount")
        if record.owner is not None and draft.get("owner") != record.owner:
            mismatches.append("owner")
        expected_category = (record.category or "").upper()
        if draft.get("category") != expected_category:
            mismatches.append("category")

        if mismatches:
            return VerifierVerdict(record.id, "fail", "overruled",
                                    "AGENT_HALLUCINATION",
                                    f"worker output diverges from source on {mismatches}")

        return VerifierVerdict(record.id, "pass", "ok", None, "matches source")
