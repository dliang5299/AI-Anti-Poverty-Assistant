#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, sys, time
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
import requests

USER_PROMPTS = [
    "Which government programs or benefits am I currently eligible for?",
    "How do I apply for benefits and what documents do I need?",
    "Are there deadlines or waiting periods I should know about for applying or maintaining eligibility?",
    "Can you explain how unemployment insurance works and how to maximize what I can receive?",
    "If I've done freelance or contract work, does that affect my unemployment eligibility or benefit amount?",
    "What options are available if I need help with rent, utilities, or food?",
    "Am I eligible for Medicaid or other healthcare assistance?",
    "Can I receive multiple types of assistance at the same time?",
    "If I start earning money again, what should I do?",
    "Are there programs that I could qualify for to help me get another job?"
]

OUTPUT_FILE = "rag_model_responses.csv"
DEFAULT_TOP_K = 5
DEFAULT_TEMPERATURE = 0.7
TIMEOUT = 60
RETRIES = 3
BACKOFF_SEC = 2.0

@dataclass
class QAResult:
    id: str
    question: str
    answer: str | None
    sources: List[Dict[str, Any]] | None
    context_used: str | None
    status: str
    error: str | None
    latency_ms: int
    timestamp: str

def call_ingest(api_url: str, bucket: str, prefix: str):
    url = api_url.rstrip("/") + "/ingest"
    r = requests.post(url, json={"bucket": bucket, "prefix": prefix}, timeout=TIMEOUT)
    return r.status_code == 200, r.text[:200]

def call_chat(api_url: str, question: str, top_k: int, temperature: float):
    url = api_url.rstrip("/") + "/chat"
    payload = {"query": question, "top_k": top_k, "temperature": temperature}
    last_err = None
    for attempt in range(1, RETRIES+1):
        t0 = time.time()
        try:
            r = requests.post(url, json=payload, timeout=TIMEOUT)
            latency = int((time.time()-t0)*1000)
            if r.status_code == 200:
                return latency, r.json(), None
            last_err = f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(BACKOFF_SEC * attempt)
    return 0, None, last_err

def write_csv(results: List[QAResult]):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id","question","answer","sources_json","context_used",
            "status","error","latency_ms","timestamp"
        ])
        w.writeheader()
        for r in results:
            w.writerow({
                "id": r.id,
                "question": r.question,
                "answer": r.answer or "",
                "sources_json": json.dumps(r.sources or [], ensure_ascii=False),
                "context_used": r.context_used or "",
                "status": r.status,
                "error": r.error or "",
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp,
            })

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", required=True, help="Base URL for RAG service (e.g., https://yourdomain.com/api)")
    p.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--ingest-bucket")
    p.add_argument("--ingest-prefix", default="")
    args = p.parse_args()

    questions = USER_PROMPTS
    if not isinstance(questions, list) or not questions:
        print("[ERROR] Embedded USER_PROMPTS is empty or not a list.", file=sys.stderr)
        sys.exit(2)

    # Optional ingestion
    if args.ingest_bucket:
        ok, msg = call_ingest(args.api_url, args.ingest_bucket, args.ingest_prefix)
        print("[INGEST]", "ok" if ok else f"ERROR: {msg}")

    results: List[QAResult] = []
    for i, q in enumerate(questions, start=1):
        qid = f"q_{i:04d}"
        print(f"[ASK] {qid}: {q}")
        latency, data, err = call_chat(args.api_url, q, args.top_k, args.temperature)
        ts = datetime.utcnow().isoformat()

        if data and not err:
            results.append(QAResult(qid, q, data.get("answer"), data.get("sources"),
                                   data.get("context_used"), "ok", None, latency, ts))
        else:
            results.append(QAResult(qid, q, None, None, None, "error", err, latency, ts))

    write_csv(results)
    print(f"✅ DONE → {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
