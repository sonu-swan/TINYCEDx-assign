from __future__ import annotations
import json
from pathlib import Path
from .transcripts import sha


def write_audit(path: str, case_id: str, seed_dir: str, pipeline_now: str,
                 role: str, threshold: float, agents: list[dict],
                 records: list[dict], events: list[dict], package_bytes: bytes):
    total_cost = 0.0
    for r in records:
        for span in r.get("agent_trace") or []:
            c = span.get("cost_usd")
            if isinstance(c, (int, float)):
                total_cost += c
    n = len(records) or 1
    latencies = sorted(
        span.get("latency_ms", 0.0) or 0.0
        for r in records for span in (r.get("agent_trace") or [])
        if span.get("latency_ms") is not None
    )
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0

    bundle = {
        "case_id": case_id,
        "pipeline_version": "tinycedx-v2",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "seed_dir": seed_dir,
        "pipeline_now": pipeline_now,
        "amendment": {"role": role, "threshold": threshold},
        "agents": agents,
        "cost": {
            "total_usd": round(total_cost, 6),
            "avg_usd_per_record": round(total_cost / n, 6),
            "p95_latency_ms": p95,
            "records": len(records),
            "projected_usd_per_10k": round((total_cost / n) * 10000, 2),
        },
        "output_package_hash": "sha256:" + __import__("hashlib").sha256(package_bytes).hexdigest(),
        "records": records,
        "events": events,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return bundle
