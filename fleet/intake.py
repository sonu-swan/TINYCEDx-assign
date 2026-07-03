from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from .models import RawRecord


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_feed(path: Path) -> list[RawRecord]:
    raw = path.read_text(encoding="utf-8")
    items = json.loads(raw)
    out = []
    for it in items:
        rid = it.get("id")
        out.append(RawRecord(
            id=rid,
            owner=it.get("owner"),
            deadline=it.get("deadline"),
            category=it.get("category"),
            notes=it.get("notes"),
            version=int(it.get("version", 1)),
            amount=_num(it.get("amount")),
            source_format="feed",
            source_version_hash=_sha(json.dumps(it, sort_keys=True)),
            raw_field_names={k: k for k in it.keys()},
        ))
    return out


# key aliases we expect to see drift on (extend as needed — this is why it generalizes:
# any KEY in this map, in any casing, maps to the canonical field)
_FIELD_ALIASES = {
    "id": "id", "owner": "owner", "deadline": "deadline", "category": "category",
    "notes": "notes", "version": "version",
    "amount": "amount", "value": "amount", "amt": "amount",
}


def _parse_kv_text(text: str) -> tuple[dict, dict]:
    """Parses 'Key: Value' lines (used by both .eml body and .pdf-extracted text).
    Returns (canonical_dict, raw_field_names) where raw_field_names maps
    canonical_key -> original_key_as_seen (for SCHEMA_DRIFT logging)."""
    canonical = {}
    raw_names = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z ]+)\s*:\s*(.+?)\s*$", line)
        if not m:
            continue
        key_raw, val = m.group(1), m.group(2)
        key_norm = key_raw.strip().lower().replace(" ", "_")
        canon = _FIELD_ALIASES.get(key_norm)
        if canon:
            canonical[canon] = val
            raw_names[canon] = key_raw.strip()
    return canonical, raw_names


def _record_from_kv(canonical: dict, raw_names: dict, source_format: str, raw_hash: str) -> RawRecord | None:
    if "id" not in canonical:
        return None
    return RawRecord(
        id=canonical.get("id"),
        owner=canonical.get("owner"),
        deadline=canonical.get("deadline"),
        category=canonical.get("category"),
        notes=canonical.get("notes"),
        version=int(canonical.get("version", 1)) if str(canonical.get("version", 1)).isdigit() else 1,
        amount=_num(canonical.get("amount")),
        source_format=source_format,
        source_version_hash=raw_hash,
        raw_field_names=raw_names,
    )


def _parse_eml(path: Path) -> RawRecord | None:
    text = path.read_text(encoding="utf-8")
    # body = everything after the first blank line (skip email headers)
    parts = text.split("\n\n", 1)
    body = parts[1] if len(parts) > 1 else text
    canonical, raw_names = _parse_kv_text(body)
    return _record_from_kv(canonical, raw_names, "eml", _sha(text))


def _parse_pdf(path: Path) -> RawRecord | None:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    canonical, raw_names = _parse_kv_text(text)
    return _record_from_kv(canonical, raw_names, "pdf", _sha(text))


def load_all(seed_dir: str) -> list[RawRecord]:
    """Persist-and-return every record from BOTH formats. Called once per run;
    the caller is responsible for persisting these (we return an explicit list,
    not a hidden in-memory global)."""
    root = Path(seed_dir)
    records: list[RawRecord] = []

    feed_path = root / "feed.json"
    if feed_path.exists():
        records.extend(_parse_feed(feed_path))

    inbox = root / "inbox"
    if inbox.exists():
        for p in sorted(inbox.glob("*.eml")):
            r = _parse_eml(p)
            if r:
                records.append(r)
        for p in sorted(inbox.glob("*.pdf")):
            r = _parse_pdf(p)
            if r:
                records.append(r)

    return records
