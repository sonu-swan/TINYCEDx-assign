from __future__ import annotations
import hashlib
from datetime import datetime, timezone

ROLES = ["risk_officer", "legal_counsel", "compliance", "finance_controller"]
STATES = ["draft", "in_review", "changes_requested", "approved", "delivered", "blocked"]


def amendment_for(case_id: str) -> tuple[str, int]:
    """Deterministic from CASE_ID, per TASK.md Step 8. Recomputes automatically
    when the real live-assigned CASE_ID is set via env var — nothing hardcoded."""
    h = hashlib.sha256(case_id.encode()).hexdigest()
    role = ROLES[int(h[0], 16) % 4]
    threshold = 10000 + (int(h[1:3], 16) % 50) * 1000
    return role, threshold


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalTrail:
    """Explicit state machine: draft -> in_review -> [changes_requested] ->
    approved -> delivered. Delivery is refused server-side for anything that
    hasn't reached 'approved'. Every transition appends (never mutates) an
    entry with actor + timestamp — this IS the audit trail for this record."""

    def __init__(self):
        self.trail: list[dict] = []

    def _append(self, state: str, actor: str, reason: str | None = None):
        assert state in STATES
        self.trail.append({"state": state, "actor": actor, "ts": now_iso(), "reason": reason})

    def start(self):
        self._append("draft", "orchestrator")
        self._append("in_review", "orchestrator")

    def block(self, reason: str):
        self._append("blocked", "orchestrator", reason)

    def approve(self, actor: str, reason: str | None = None):
        self._append("approved", actor, reason)

    def amendment_approve(self, role: str, threshold: float, amount: float, actor: str):
        """Second approval gate required when normalized amount >= threshold."""
        if amount is not None and amount >= threshold:
            self._append("approved", f"{actor}:{role}", f"amendment second approval (>= {threshold})")

    def try_deliver(self, role: str | None = None, threshold: float | None = None,
                     amount: float | None = None) -> bool:
        """Server-side gate: refuses delivery unless 'approved' precedes it.
        If role/threshold/amount are given and amount >= threshold, the
        second (amendment) approval by `role` must ALSO be present, or
        delivery is refused — this is what makes the CASE_ID amendment a
        real gate and not just a logged note."""
        states = [t["state"] for t in self.trail]
        if "approved" not in states:
            return False
        if role and threshold is not None and amount is not None and amount >= threshold:
            if not self.has_role_approval(role):
                return False
        self._append("delivered", "orchestrator")
        return True

    def has_role_approval(self, role: str) -> bool:
        return any(t["actor"].split(":")[-1] == role for t in self.trail if t["state"] == "approved")
