from __future__ import annotations
import json, sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("usage: cli_replay.py <record_id>"); sys.exit(1)
    rid = sys.argv[1]
    audit = json.loads(open("out/audit.json").read())
    rec = next((r for r in audit["records"] if r["id"] == rid), None)
    if not rec:
        print(f"FAIL: no record {rid}"); sys.exit(1)

    print(f"=== data lineage for {rid} (reconstructed from audit.json + transcripts/ only) ===")
    print(f"source_format={rec['source_format']} source_version_hash={rec['source_version_hash']}")
    print(f"final status={rec['status']}")
    if rec.get("transcript_hash"):
        th = rec["transcript_hash"].split(":")[-1]
        tpath = Path("transcripts") / f"{th}.json"
        if tpath.exists():
            t = json.loads(tpath.read_text())
            print(f"delivered_fields sourced from transcript {tpath.name}, "
                  f"produced by agent={t.get('agent')} model={t.get('model')}")
            print(f"transcript response == delivered_fields: "
                  f"{t.get('response') == rec.get('delivered_fields')}")
    for span in rec.get("agent_trace") or []:
        print(f"  step: {span['agent']} -> status={span['status']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
