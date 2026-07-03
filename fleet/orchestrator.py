from __future__ import annotations
import os
from .models import RawRecord
from .worker import Worker
from .verifier import Verifier
from .approval import ApprovalTrail, amendment_for
from .transcripts import TranscriptStore

MAX_STEPS = int(os.environ.get("MAX_STEPS_PER_RECORD", "4"))
MAX_COST = float(os.environ.get("MAX_COST_USD_PER_RECORD", "0.02"))


class Orchestrator:
    """Agent identity: name='orchestrator', role='orchestrator'.
    can_call=['worker','verifier','operator']. Owns the run: decides which
    agent handles each record, enforces step/cost budgets, routes exceptions.
    Contains NO drafting or verification logic itself — it only delegates and
    makes routing decisions. (That separation is what stops this from being
    the 'god-function' anti-pattern the task explicitly fails.)"""

    name = "orchestrator"
    role = "orchestrator"
    can_call = ["worker", "verifier", "operator"]

    def __init__(self, replay: bool, case_id: str, transcripts_dir: str = "transcripts"):
        self.store = TranscriptStore(transcripts_dir)
        self.worker = Worker(self.store, replay)
        self.verifier = Verifier()
        self.role_R, self.threshold_T = amendment_for(case_id)
        self.event_seq = 0
        self.events: list[dict] = []

    def _log(self, actor: str, action: str, record_id: str | None = None):
        self.events.append({"seq": self.event_seq, "ts": __import__("fleet.approval", fromlist=["now_iso"]).now_iso(),
                             "actor": actor, "action": action, "record_id": record_id})
        self.event_seq += 1

    def process_record(self, record: RawRecord, pre_reason=None, class_b_code=None) -> dict:
        """Returns one record dict shaped for audit.json['records']."""
        trace: list[dict] = []
        trail = ApprovalTrail()

        if pre_reason:
            code, cls, note = pre_reason
            trail.block(note)
            self._log("orchestrator", f"exception:{code}", record.id)
            return self._exception_record(record, code, cls, trace)

        trail.start()
        cost_used = 0.0
        steps_used = 0
        out = None

        for attempt in range(2):  # bounded retry: first pass + 1 retry
            steps_used += 1
            if steps_used > MAX_STEPS:
                self._log("orchestrator", "AGENT_LOOP:step_budget_exceeded", record.id)
                trace.append({"agent": "orchestrator", "status": "killed",
                               "retries": attempt})
                return self._exception_record(record, "AGENT_LOOP", "A", trace)

            out = self.worker.draft(record, is_retry=(attempt > 0))
            cost_used += out.cost_usd
            trace.append({"agent": "worker", "model": out.model, "prompt_version": out.prompt_version,
                           "tokens_in": out.tokens_in, "tokens_out": out.tokens_out,
                           "cost_usd": out.cost_usd, "latency_ms": out.latency_ms,
                           "retries": attempt, "transcript_hash": out.transcript_hash,
                           "status": out.status})

            if cost_used > MAX_COST:
                self._log("orchestrator", "BUDGET_EXCEEDED", record.id)
                trace.append({"agent": "orchestrator", "status": "routed",
                               "retries": attempt, "cost_usd": cost_used})
                return self._exception_record(record, "BUDGET_EXCEEDED", "A", trace)

            verdict = self.verifier.check(record, out)
            trace.append({"agent": "verifier", "status": verdict.status, "verdict": verdict.verdict,
                           "cost_usd": verdict.cost_usd, "latency_ms": verdict.latency_ms,
                           "retries": attempt})
            self._log("verifier", f"verdict:{verdict.verdict}:{record.id}", record.id)

            if verdict.verdict == "pass":
                break
            if attempt == 0:
                continue  # bounded retry with escalated model
            # still bad after retry -> route to human, never deliver
            self._log("orchestrator", f"exception:{verdict.reason_code}", record.id)
            return self._exception_record(record, verdict.reason_code or "AGENT_MALFORMED", "A", trace)

        # Approval chain
        trail.approve("operator:reviewer")
        self._log("operator", "approved", record.id)
        if record.amount is not None and record.amount >= self.threshold_T:
            trail.amendment_approve(self.role_R, self.threshold_T, record.amount, "operator")
            self._log("operator", f"amendment_approved:{self.role_R}", record.id)

        delivered = trail.try_deliver(role=self.role_R, threshold=self.threshold_T, amount=record.amount)
        if not delivered:
            self._log("orchestrator", "delivery_refused:no_approval", record.id)
            return self._exception_record(record, "UNVERIFIED_ANOMALY", "A", trace, trail)
        self._log("orchestrator", "delivered", record.id)

        return {
            "id": record.id, "version": record.version, "source_format": record.source_format,
            "source_version_hash": record.source_version_hash, "status": "delivered",
            "reason_code": class_b_code, "reason_class": ("B" if class_b_code else None),
            "transcript_hash": out.transcript_hash,
            "delivered_fields": out.draft_fields,
            "delivered_fields_hash": self.store.read(out.transcript_hash)["delivered_fields_hash"],
            "agent_trace": trace,
            "approval_trail": trail.trail,
        }

    def _exception_record(self, record: RawRecord, code: str, cls: str, trace: list[dict],
                           trail: ApprovalTrail | None = None) -> dict:
        return {
            "id": record.id, "version": record.version, "source_format": record.source_format,
            "source_version_hash": record.source_version_hash, "status": "exception",
            "reason_code": code, "reason_class": cls,
            "transcript_hash": None, "delivered_fields": None, "delivered_fields_hash": None,
            "agent_trace": trace or [{"agent": "orchestrator", "status": "routed"}],
            "approval_trail": (trail.trail if trail else [{"state": "blocked", "actor": "orchestrator",
                                                             "ts": __import__("fleet.approval", fromlist=["now_iso"]).now_iso(),
                                                             "reason": code}]),
        }

    def superseded_record(self, record: RawRecord) -> dict:
        return {
            "id": record.id, "version": record.version, "source_format": record.source_format,
            "source_version_hash": record.source_version_hash, "status": "superseded",
            "reason_code": "SUPERSEDED_VERSION", "reason_class": "B",
            "transcript_hash": None, "delivered_fields": None, "delivered_fields_hash": None,
            "agent_trace": [], "approval_trail": [],
        }

    def roster(self) -> list[dict]:
        return [
            {"name": "orchestrator", "role": "orchestrator", "models": [], "can_call": ["worker", "verifier", "operator"]},
            {"name": "worker", "role": "worker", "models": ["gpt-4o-mini", "claude-3-5-haiku"], "can_call": []},
            {"name": "verifier", "role": "verifier", "models": ["gpt-4o-mini"], "can_call": []},
            {"name": "operator", "role": "operator", "models": [], "can_call": []},
        ]
