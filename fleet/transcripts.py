from __future__ import annotations
import json, hashlib
from pathlib import Path


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(obj) -> str:
    return "sha256:" + hashlib.sha256(canon(obj)).hexdigest()


class TranscriptStore:
    """Commits/reads /transcripts/<hex>.json. Filename == hex of response_hash,
    exactly as verify_audit.py check #8/#14 require."""

    def __init__(self, root: str = "transcripts"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def commit(self, agent: str, model: str, prompt_version: str, request: dict, response: dict) -> dict:
        response_hash = sha(response)
        delivered_fields_hash = sha(response)
        stem = response_hash.split(":")[-1]
        payload = {
            "agent": agent,
            "model": model,
            "prompt_version": prompt_version,
            "request": request,
            "response": response,
            "response_hash": response_hash,
            "delivered_fields_hash": delivered_fields_hash,
        }
        (self.root / f"{stem}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def read(self, response_hash: str) -> dict | None:
        stem = response_hash.split(":")[-1]
        p = self.root / f"{stem}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
