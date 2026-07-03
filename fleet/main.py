from __future__ import annotations
import json, os, sys
from pathlib import Path

from .intake import load_all
from .detectors import resolve_versions, classify_batch
from .orchestrator import Orchestrator
from .audit import write_audit


def run(seed_dir: str, out_dir: str = "out", transcripts_dir: str = "transcripts"):
    replay = os.environ.get("REPLAY_LLM", "true").lower() != "false"
    case_id = os.environ.get("CASE_ID", "CEDX-XXXX")
    pipeline_now = os.environ.get("PIPELINE_NOW", "2026-06-26")

    print(f"[intake] parsing {seed_dir} (feed.json + inbox/) ...")
    raw = load_all(seed_dir)
    print(f"[intake] {len(raw)} raw records persisted")

    kept, superseded, schema_drift = resolve_versions(raw)
    print(f"[orchestration] {len(kept)} current-version records, "
          f"{len(superseded)} superseded, {len(schema_drift)} with schema drift")

    classifications = classify_batch(kept, pipeline_now)

    orch = Orchestrator(replay=replay, case_id=case_id, transcripts_dir=transcripts_dir)
    print(f"AMENDMENT: role={orch.role_R} threshold={orch.threshold_T}")
    orch._log("orchestrator", "run_start")

    out_records = []
    for r in superseded:
        out_records.append(orch.superseded_record(r))

    for rid, record in kept.items():
        pre = classifications.get(rid)
        cb_code = "SCHEMA_DRIFT" if (rid in schema_drift and pre is None) else None
        rec_out = orch.process_record(record, pre_reason=pre, class_b_code=cb_code)
        out_records.append(rec_out)
        print(f"  {rid}: status={rec_out['status']} reason={rec_out.get('reason_code')}")

    orch._log("orchestrator", "run_end")

    delivered = [r for r in out_records if r["status"] == "delivered"]
    exceptions = [r for r in out_records if r["status"] == "exception"]

    package = {
        "case_id": case_id,
        "items": [r["delivered_fields"] for r in delivered],
    }
    package_bytes = json.dumps(package, indent=2, sort_keys=True).encode("utf-8")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "branded_package.json").write_bytes(package_bytes)

    exq = {
        "exceptions": [
            {"id": r["id"], "reason_code": r["reason_code"], "reason_class": r["reason_class"]}
            for r in exceptions
        ]
    }
    (Path(out_dir) / "exception_queue.json").write_text(json.dumps(exq, indent=2), encoding="utf-8")

    bundle = write_audit(
        path=str(Path(out_dir) / "audit.json"),
        case_id=case_id, seed_dir=seed_dir, pipeline_now=pipeline_now,
        role=orch.role_R, threshold=orch.threshold_T,
        agents=orch.roster(), records=out_records, events=orch.events,
        package_bytes=package_bytes,
    )
    print(f"[delivery] {len(delivered)} delivered, {len(exceptions)} exceptions, "
          f"{len(superseded)} superseded, cost=${bundle['cost']['total_usd']}")
    return bundle


if __name__ == "__main__":
    seed_dir = os.environ.get("SEED_DIR", "seed")
    run(seed_dir)
