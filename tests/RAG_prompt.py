#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# -----------------------------
# Defaults & built-in prompts
# -----------------------------
USER_PROMPTS: List[str] = [
    "Which government programs or benefits am I currently eligible for?",
    "How do I apply for benefits and what documents do I need?",
    "Are there deadlines or waiting periods I should know about for applying or maintaining eligibility?",
    "Can you explain how unemployment insurance works and how to maximize what I can receive?",
    "If I've done freelance or contract work, does that affect my unemployment eligibility or benefit amount?",
    "What options are available if I need help with rent, utilities, or food?",
    "Am I eligible for Medicaid or other healthcare assistance?",
    "What happens if my benefits application is denied—can I appeal and how?",
    "How do I report changes in my income or employment to keep benefits compliant?",
    "What local resources or nonprofits can help me with applications or legal aid?",
]

today = datetime.today().strftime("%Y-%m-%d")
OUTPUT_FILE = f"tests/{today}_rag_model_responses.csv"
TIMEOUT = 60               # seconds for per-request timeout
RETRIES = 3
BACKOFF_SEC = 2.0          # simple linear backoff (attempt * BACKOFF_SEC)

# -----------------------------
# Data structures
# -----------------------------
@dataclass
class QAResult:
    id: str
    question: str
    answer: Optional[str]
    sources: Optional[List[Dict[str, Any]]]
    programs: Optional[List[str]]
    status: str              # "ok" | "error"
    error: Optional[str]
    latency_ms: int
    timestamp: str

# -----------------------------
# Helpers
# -----------------------------
def load_prompts(prompts_file: Optional[str]) -> List[str]:
    if not prompts_file:
        return USER_PROMPTS
    try:
        # If JSON: expect list[str]
        if prompts_file.lower().endswith(".json"):
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
                    raise ValueError("JSON prompts file must be a list of strings.")
                return data
        # If TXT: one question per line (non-empty)
        with open(prompts_file, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines()]
            return [ln for ln in lines if ln]
    except Exception as e:
        print(f"[ERROR] Failed to load prompts file '{prompts_file}': {e}", file=sys.stderr)
        sys.exit(2)

def call_ingest(api_url: str, bucket: str, prefix: str) -> tuple[bool, str]:
    url = api_url.rstrip("/") + "/ingest"
    try:
        r = requests.post(url, json={"bucket": bucket, "prefix": prefix}, timeout=TIMEOUT)
        ok = r.status_code == 200
        return ok, (r.text[:200] if not ok else "ok")
    except Exception as e:
        return False, str(e)

def call_chat(
    api_url: str,
    question: str,
    *,
    situation: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> tuple[int, Optional[Dict[str, Any]], Optional[str]]:
    """
    Calls /chat with payload that matches the FastAPI schema:
      ChatRequest: { message: str, situation?: str, conversation_history?: List[Dict] }
    Returns (latency_ms, json_or_none, error_or_none)
    """
    url = api_url.rstrip("/") + "/chat"
    payload: Dict[str, Any] = {"message": question}
    if situation is not None:
        payload["situation"] = situation
    if conversation_history is not None:
        payload["conversation_history"] = conversation_history

    last_err: Optional[str] = None
    for attempt in range(1, RETRIES + 1):
        t0 = time.time()
        try:
            r = requests.post(url, json=payload, timeout=TIMEOUT)
            latency = int((time.time() - t0) * 1000)
            if r.status_code == 200:
                return latency, r.json(), None
            last_err = f"HTTP {r.status_code}: {r.text[:400]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(BACKOFF_SEC * attempt)
    return 0, None, last_err

def write_csv(results: List[QAResult]) -> None:
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "question",
                "answer",
                "sources_json",
                "programs_json",
                "status",
                "error",
                "latency_ms",
                "timestamp",
            ],
        )
        w.writeheader()
        for r in results:
            row = {
                "id": r.id,
                "question": r.question,
                "answer": r.answer or "",
                "sources_json": json.dumps(r.sources or [], ensure_ascii=False),
                "programs_json": json.dumps(r.programs or [], ensure_ascii=False),
                "status": r.status,
                "error": r.error or "",
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp,
            }
            w.writerow(row)

# -----------------------------
# CLI
# -----------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--api-url",
        required=True,
        help="Base URL for RAG service (e.g., http://localhost:8000)",
    )
    # Kept for future use / parity; server doesn't currently take these in the request
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--temperature", type=float, default=0.7)

    p.add_argument("--ingest-bucket", help="Optional S3 bucket to ingest before asking questions")
    p.add_argument("--ingest-prefix", default="", help="Optional S3 prefix for ingestion")
    p.add_argument("--prompts-file", help="Optional JSON (list[str]) or TXT (one per line) prompts file")
    p.add_argument("--situation", help="Optional situation string sent to /chat")
    p.add_argument("--with-history", action="store_true", help="Accumulate conversation_history across questions")

    args = p.parse_args()

    questions = load_prompts(args.prompts_file)
    if not questions:
        print("[ERROR] No questions to ask.", file=sys.stderr)
        sys.exit(2)

    if args.ingest_bucket:
        ok, msg = call_ingest(args.api_url, args.ingest_bucket, args.ingest_prefix)
        print("[INGEST]", "ok" if ok else f"ERROR: {msg}")

    results: List[QAResult] = []
    history: List[Dict[str, Any]] = []

    for i, q in enumerate(questions, start=1):
        qid = f"Q{i:03d}"
        print(f"[ASK] {qid}: {q}")

        hist_to_send = history if args.with_history else None
        latency, data, err = call_chat(
            args.api_url,
            q,
            situation=args.situation,
            conversation_history=hist_to_send,
        )
        ts = datetime.utcnow().isoformat()

        if data and not err:
            # API returns: {response: str, sources: List[Dict], programs: List[str]}
            answer = data.get("response")
            sources = data.get("sources")
            programs = data.get("programs")

            # optionally build history for the next turn
            if args.with_history:
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": answer or ""})

            results.append(
                QAResult(
                    id=qid,
                    question=q,
                    answer=answer,
                    sources=sources,
                    programs=programs,
                    status="ok",
                    error=None,
                    latency_ms=latency,
                    timestamp=ts,
                )
            )
        else:
            results.append(
                QAResult(
                    id=qid,
                    question=q,
                    answer=None,
                    sources=None,
                    programs=None,
                    status="error",
                    error=err,
                    latency_ms=latency,
                    timestamp=ts,
                )
            )

    write_csv(results)
    print(f"✅ DONE → {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
