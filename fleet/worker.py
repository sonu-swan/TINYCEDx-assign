from __future__ import annotations
import os, time
from .models import RawRecord, WorkerOutput
from .router import pick_model, cost_for
from .transcripts import TranscriptStore, sha

PROMPT_VERSION = "worker-v1"
REQUIRED_KEYS = {"id", "owner", "category", "amount", "deadline", "branded_summary"}


class Worker:
    """Agent identity: name='worker', role='worker'. can_call=[] (leaf agent).
    Drafts the branded output for one record. Never checks its own work —
    that's the Verifier's job (separation of duties, see ARCHITECTURE.md)."""

    name = "worker"
    role = "worker"
    can_call: list[str] = []

    def __init__(self, store: TranscriptStore, replay: bool):
        self.store = store
        self.replay = replay

    def draft(self, record: RawRecord, is_retry: bool = False) -> WorkerOutput:
        model = pick_model(record.notes or "", is_retry)
        request = {
            "record_id": record.id,
            "prompt_version": PROMPT_VERSION,
            "source_hash": record.source_version_hash,
            "is_retry": is_retry,
        }
        t0 = time.time()

        if self.replay:
            # Deterministic replay path: the response is COMMITTED content,
            # not invented at request time. This is what makes REPLAY_LLM=true
            # reproducible and auditable.
            response = self._simulated_llm_response(record)
        else:
            response = self._call_real_llm(record, model)  # pragma: no cover (needs LLM_API_KEY)

        latency_ms = round((time.time() - t0) * 1000, 2)
        tokens_in = 120 + len(record.notes or "")
        tokens_out = 60
        cost = cost_for(model, tokens_in, tokens_out)

        committed = self.store.commit(self.name, model, PROMPT_VERSION, request, response)
        thash = committed["response_hash"]

        if not REQUIRED_KEYS.issubset(response.keys()):
            return WorkerOutput(record.id, None, model, PROMPT_VERSION, tokens_in, tokens_out,
                                 cost, latency_ms, 0, "abstained", thash,
                                 abstain_reason="malformed draft (missing required fields)")

        return WorkerOutput(record.id, response, model, PROMPT_VERSION, tokens_in, tokens_out,
                             cost, latency_ms, 0, "ok", thash)

    def _simulated_llm_response(self, record: RawRecord) -> dict:
        """Stand-in for the model call in offline/replay mode: deterministically
        derives the branded draft FROM the source record (never invents values).
        In REPLAY_LLM=false mode this is replaced by a real API call (see
        _call_real_llm) whose transcript gets committed the same way."""
        return {
            "id": record.id,
            "owner": record.owner,
            "category": (record.category or "").upper(),
            "amount": record.amount,
            "deadline": record.deadline,
            "branded_summary": f"CEDX work item {record.id} ({record.category}) "
                                f"for {record.owner}, amount {record.amount}.",
        }

    def _call_real_llm(self, record: RawRecord, model: str) -> dict:  # pragma: no cover
        import json, urllib.request
        api_key = os.environ["LLM_API_KEY"]
        base_url = os.environ.get("LLM_BASE_URL", "https://api.anthropic.com/v1/messages")
        prompt = (
            "You are the Worker agent in a CEDX pipeline. Given this source record, "
            "produce ONLY a JSON object with keys id, owner, category, amount, deadline, "
            "branded_summary. Never invent a field or value not present in the source.\n"
            f"SOURCE: {json.dumps(record.__dict__)}"
        )
        body = json.dumps({
            "model": model, "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(base_url, data=body, headers={
            "Content-Type": "application/json", "x-api-key": api_key,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return json.loads(text)
