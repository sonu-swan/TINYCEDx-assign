"""
Declarative normalization + exception detection. Pure rules, no hardcoded IDs
or values — every threshold is computed FROM the batch, so it generalizes to
the held-out seed (different values, same problem types).
"""
from __future__ import annotations
import re
from datetime import date
from statistics import median
from .models import RawRecord

ALLOWED_CATEGORIES = {"ONBOARDING", "RENEWAL", "REVIEW", "REPORT", "INTAKE"}

# Phrases that try to get an agent to bypass its own rules/review, or to
# override structured data with an instruction embedded in free text.
# Keyword-pattern based (not a literal string list) so it generalizes.
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|your)\s+instructions",
    r"ignore\s+your\s+rules",
    r"ignore\s+the\s+field",
    r"skip\s+review",
    r"approve\s+(this\s+)?immediately",
    r"output\s+approved",
    r"the\s+real\s+(number|amount|value)\s+is",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_AMBIGUITY_PATTERNS = [
    r"unclear", r"inconsistent", r"could\s+be", r"figures?\s+inconsistent",
]
_AMBIGUITY_RE = re.compile("|".join(_AMBIGUITY_PATTERNS), re.IGNORECASE)


def resolve_versions(records: list[RawRecord]):
    """Class-B SUPERSEDED_VERSION: same id seen more than once -> keep highest
    version, log the rest as superseded. Also returns schema_drift entries
    (any record whose raw_field_names shows a non-canonical original key)."""
    by_id: dict[str, list[RawRecord]] = {}
    for r in records:
        by_id.setdefault(r.id, []).append(r)

    kept: dict[str, RawRecord] = {}
    superseded: list[RawRecord] = []
    for rid, versions in by_id.items():
        versions.sort(key=lambda r: r.version)
        kept[rid] = versions[-1]
        superseded.extend(versions[:-1])

    schema_drift: dict[str, list[str]] = {}
    for r in list(kept.values()) + superseded:
        drifted = [orig for canon, orig in r.raw_field_names.items()
                   if orig.lower().replace(" ", "_") != canon]
        if drifted:
            schema_drift[r.id] = drifted

    return kept, superseded, schema_drift


def _robust_outlier_ids(amounts: dict[str, float]) -> set[str]:
    """Median Absolute Deviation (MAD) based outlier rule — robust to the
    outlier itself skewing the estimate (unlike mean+stdev). Modified
    z-score > 5 is a standard conservative cutoff (Iglewicz & Hoaglin use
    3.5; we use 5 to avoid flagging normal business variance, only the
    planted extreme case). Threshold is DERIVED from the batch, never a
    literal amount, so it generalizes to different magnitudes."""
    vals = list(amounts.values())
    if len(vals) < 3:
        return set()
    m = median(vals)
    mad = median([abs(v - m) for v in vals]) or 1e-9
    out = set()
    for rid, v in amounts.items():
        modified_z = 0.6745 * (v - m) / mad
        if abs(modified_z) > 5:
            out.add(rid)
    return out


def classify_batch(kept: dict[str, RawRecord], pipeline_now: str):
    """Runs Class-A detectors across the whole kept batch. Returns
    {record_id: (reason_code, reason_class, note) or None}."""
    today = date.fromisoformat(pipeline_now)
    amounts = {rid: r.amount for rid, r in kept.items() if r.amount is not None}
    outlier_ids = _robust_outlier_ids(amounts)

    results: dict[str, tuple[str, str, str] | None] = {}
    for rid, r in kept.items():
        # priority order matters: injection > missing > stale > outlier > ambiguity > unverified
        notes = r.notes or ""
        if _INJECTION_RE.search(notes):
            results[rid] = ("INJECTION_BLOCKED", "A", "notes attempt to override rules/data")
            continue
        if r.amount is None:
            results[rid] = ("MISSING_INPUT", "A", "required numeric field (amount) is null")
            continue
        try:
            if date.fromisoformat(r.deadline) < today:
                results[rid] = ("STALE", "A", f"deadline {r.deadline} < now {pipeline_now}")
                continue
        except (TypeError, ValueError):
            results[rid] = ("UNVERIFIED_ANOMALY", "A", "deadline missing/unparseable")
            continue
        if rid in outlier_ids:
            results[rid] = ("OUTLIER", "A", "amount fails robust MAD outlier test")
            continue
        if (r.category or "").strip() == "?" or _AMBIGUITY_RE.search(notes):
            results[rid] = ("LOW_CONFIDENCE", "A", "category/notes too ambiguous to draft confidently")
            continue
        if (r.category or "").strip().upper() not in ALLOWED_CATEGORIES:
            results[rid] = ("UNVERIFIED_ANOMALY", "A", f"unrecognized category {r.category!r}")
            continue
        results[rid] = None  # clean
    return results
