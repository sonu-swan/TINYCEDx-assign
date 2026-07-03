"""
Typed contracts. Every agent in the fleet consumes/produces ONLY these shapes.
No free-form string passing between agents (that's the "markdown" anti-pattern
the task calls out).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class RawRecord:
    """What Intake produces. One per source row, before any cleanup."""
    id: str
    owner: Optional[str]
    deadline: Optional[str]
    category: Optional[str]
    notes: Optional[str]
    version: int
    amount: Optional[float]
    source_format: str          # "feed" | "eml" | "pdf"
    source_version_hash: str
    raw_field_names: dict = field(default_factory=dict)  # for SCHEMA_DRIFT logging


@dataclass
class OrchestratorDecision:
    """What Orchestrator hands to Worker, or the exception it raises instead."""
    record: RawRecord
    proceed: bool
    reason_code: Optional[str] = None   # set if proceed=False
    reason_class: Optional[str] = None  # "A" or "B" or None
    note: Optional[str] = None


@dataclass
class WorkerOutput:
    """What Worker hands to Verifier."""
    record_id: str
    draft_fields: Optional[dict]        # None if abstained
    model: str
    prompt_version: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    retries: int
    status: str                         # ok | retried | abstained | killed
    transcript_hash: Optional[str]
    abstain_reason: Optional[str] = None


@dataclass
class VerifierVerdict:
    """What Verifier hands back to Orchestrator. Can OVERRULE the Worker."""
    record_id: str
    verdict: str                        # pass | fail | needs_human
    status: str                         # ok | rejected | overruled
    reason_code: Optional[str] = None   # AGENT_HALLUCINATION / AGENT_MALFORMED / None
    note: Optional[str] = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0
