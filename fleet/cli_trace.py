from __future__ import annotations
import json, sys


def main():
    if len(sys.argv) < 2:
        print("usage: cli_trace.py <record_id>"); sys.exit(1)
    rid = sys.argv[1]
    audit = json.loads(open("out/audit.json").read())
    rec = next((r for r in audit["records"] if r["id"] == rid), None)
    if not rec:
        print(f"FAIL: no record {rid} in out/audit.json"); sys.exit(1)

    print(f"=== agent decision path for {rid} ===")
    print(f"status={rec['status']} reason={rec.get('reason_code')} class={rec.get('reason_class')}")
    for span in rec.get("agent_trace") or []:
        cost = span.get("cost_usd")
        print(f"  [{span['agent']:12}] status={span['status']:9} "
              f"model={span.get('model')} verdict={span.get('verdict')} "
              f"cost=${cost if cost is not None else 0} "
              f"latency={span.get('latency_ms')}ms retries={span.get('retries')}")
    print("--- approval trail ---")
    for t in rec.get("approval_trail") or []:
        print(f"  {t['state']:18} actor={t['actor']:20} ts={t['ts']} reason={t.get('reason')}")
    sys.exit(0)


if __name__ == "__main__":
    main()
