"""
Router policy (documented in DECISIONS.md too):
  - Default: cheap model (gpt-4o-mini) for every record.
  - Escalate to a stronger model (claude-3-5-haiku) ONLY when:
      a) this is a RETRY after the Verifier rejected the first draft, or
      b) the record's notes are long/dense (> NOTES_ESCALATE_CHARS) — a proxy
         for cases likely to need more careful reading, not a hardcoded id.
Both signals are computed from the record itself, so this generalizes to the
held-out set without any per-id logic.
"""
CHEAP_MODEL = "gpt-4o-mini"
STRONG_MODEL = "claude-3-5-haiku"
NOTES_ESCALATE_CHARS = 80

CHEAP_COST_PER_1K_TOKENS = 0.00015
STRONG_COST_PER_1K_TOKENS = 0.0015


def pick_model(notes: str, is_retry: bool) -> str:
    if is_retry or len(notes or "") > NOTES_ESCALATE_CHARS:
        return STRONG_MODEL
    return CHEAP_MODEL


def cost_for(model: str, tokens_in: int, tokens_out: int) -> float:
    rate = STRONG_COST_PER_1K_TOKENS if model == STRONG_MODEL else CHEAP_COST_PER_1K_TOKENS
    return round(rate * (tokens_in + tokens_out) / 1000.0, 6)
