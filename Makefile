SEED_DIR ?= seed
export SEED_DIR
export PYTHONPATH := .

.PHONY: demo verify trace eval replay probe-approval probe-agent-failure probe-budget \
        probe-append-only probe-idempotency probe-crash clean

demo:
	python3 -m fleet.main

verify:
	python3 verify_audit.py --audit out/audit.json --transcripts transcripts --schema audit.schema.json

trace:
	python3 -m fleet.cli_trace $(ID)

eval:
	python3 -m fleet.eval_harness

replay:
	python3 -m fleet.cli_replay $(ID)

probe-approval:
	python3 fleet/probes/probe_approval.py

probe-agent-failure:
	python3 fleet/probes/probe_agent_failure.py

probe-budget:
	python3 fleet/probes/probe_budget.py

probe-append-only:
	python3 fleet/probes/probe_append_only.py

probe-idempotency:
	python3 fleet/probes/probe_idempotency.py

probe-crash:
	@echo "TODO (bonus, not implemented)"; false

clean:
	rm -rf out
