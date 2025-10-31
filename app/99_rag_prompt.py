#!/usr/bin/env python3
"""
rag_batch_eval_inline.py

Run a batch of questions against a RAG FastAPI service WITHOUT needing a CSV/JSONL.
You can either:
  A) Edit the QUESTIONS list in this file, or
  B) Point to an existing Python module (e.g., your 99_baseline_prompt.py) and a variable name
     that contains your list of questions.

Usage examples:

# A) Use the in-file QUESTIONS list
python rag_batch_eval_inline.py --api-url https://yourdomain.com/api --output results.jsonl

# B) Load questions from your script (variable name defaults to QUESTIONS)
python rag_batch_eval_inline.py \
  --api-url https://yourdomain.com/api \
  --module-path /path/to/99_baseline_prompt.py \
  --var-name QUESTIONS \
  --output results.csv \
  --format csv

Optional: trigger ingestion before asking
  --ingest-bucket your-bucket --ingest-prefix rag-knowledge/

Output fields:
id, question, answer, sources/context, status, error, latency_ms, timestamp
"""
from __future__ import annotations
import argparse, csv, json, sys, time, uuid, importlib.util
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from datetime import datetime

import requests

# =====================
# OPTION A: inline list
# =====================
# Edit this if you want to hardcode your questions here.
QUESTIONS: list[str] = [
    # "What is this document about?",
    # "How does this RAG system combine OpenAI with Claude?",
    # "What steps are needed to deploy to ECS Fargate?",
]

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

def _load_from_module(module_path: str, var_name: str) -> list[str]:
    """Load questions from a Python module file.
    The variable can be:
      - list[str]
      - list[dict] with keys 'question' or 'prompt'
    """
    spec = importlib.util.spec_from_file_location("external_questions", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    if not hasattr(mod, var_name):
        raise AttributeError(f"Variable '{var_name}' not found in {module_path}")
    data = getattr(mod, var_name)

    questions: list[str] = []
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                questions.append(item)
            elif isinstance(item, dict):
                # support {'question': '...'} or {'prompt':'...'}
                if "question" in item and isinstance(item["question"], str):
                    questions.append(item["question"])
                elif "prompt" in item and isinstance(item["prompt"], str):
                    questions.append(item["prompt"])
                else:
                    raise TypeError(f"Item {i} is a dict but missing 'question'/'prompt' string")
            else:
                raise TypeError(f"Item {i} is neither str nor dict: {type(item)}")
    else:
        raise TypeError(f"'{var_name}' must be a list; got {type(data)}")

    if not questions:
        raise ValueError("No questions were loaded from the module")
    return questions

def _ingest(api_url: str, bucket: str, prefix: str) -> tuple[bool, str]:
    url = api_url.rstrip("/") + "/ingest"
    payload = {"bucket": bucket, "prefix": prefix}
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        if resp.status_code == 200:
            return True, "ok"
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return False, str(e)

def _ask(api_url: str, question: str, top_k: int, temperature: float) -> tuple[int, dict | None, str | None]:
    url = api_url.rstrip("/") + "/chat"
    payload = {"query": question, "top_k": top_k, "temperature": temperature}
    last_err = None
    for attempt in range(1, RETRIES + 1):
        t0 = time.time()
        try:
            resp = requests.post(url, json=payload, timeout=TIMEOUT)
            latency_ms = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return latency_ms, resp.json(), None
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as e:
            last_err = str(e)
        if attempt < RETRIES:
            time.sleep(BACKOFF_SEC * attempt)
    return 0, None, last_err

def _write_output_csv(path: str, results: List[QAResult]) -> None:
    fieldnames = ["id","question","answer","sources_json","context_used","status","error","latency_ms","timestamp"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for res in results:
            row = {
                "id": res.id,
                "question": res.question,
                "answer": res.answer or "",
                "sources_json": json.dumps(res.sources or [], ensure_ascii=False),
                "context_used": res.context_used or "",
                "status": res.status,
                "error": res.error or "",
                "latency_ms": res.latency_ms,
                "timestamp": res.timestamp,
            }
            w.writerow(row)

def _write_output_jsonl(path: str, results: List[QAResult]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for res in results:
            obj = {
                "id": res.id,
                "question": res.question,
                "answer": res.answer,
                "sources": res.sources,
                "context_used": res.context_used,
                "status": res.status,
                "error": res.error,
                "latency_ms": res.latency_ms,
                "timestamp": res.timestamp,
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser(description="Batch evaluate questions against a RAG /chat API without CSV")
    ap.add_argument("--api-url", required=True, help="Base URL for RAG service (e.g., https://yourdomain.com/api or http://localhost:8000)")
    ap.add_argument("--output", required=True, help="Output file (.csv or .jsonl)")
    ap.add_argument("--format", choices=["csv","jsonl"], default="jsonl", help="Output format")
    ap.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--ingest-bucket", help="If provided, trigger ingestion before questions")
    ap.add_argument("--ingest-prefix", default="", help="S3 prefix for ingestion")
    ap.add_argument("--module-path", help="Path to Python file that contains the questions list (e.g., 99_baseline_prompt.py)")
    ap.add_argument("--var-name", default="QUESTIONS", help="Variable name inside the module with the list (default: QUESTIONS)")

    args = ap.parse_args()

    # Load questions from either module or inline list
    if args.module_path:
        questions = _load_from_module(args.module_path, args.var_name)
    else:
        questions = list(QUESTIONS)

    if not questions:
        print("[ERROR] No questions provided. Either edit QUESTIONS[] in this file or use --module-path/--var-name.", file=sys.stderr)
        sys.exit(2)

    # Optional ingestion
    if args.ingest_bucket:
        ok, msg = _ingest(args.api_url, args.ingest_bucket, args.ingest_prefix or "")
        if not ok:
            print(f"[INGEST][ERROR] {msg}", file=sys.stderr)
        else:
            print("[INGEST] Triggered successfully")

    print(f"[INFO] Loaded {len(questions)} questions")

    results: List[QAResult] = []
    for idx, q in enumerate(questions, start=1):
        qid = f"q_{idx:04d}"
        print(f"[ASK] {qid}: {q}")
        latency_ms, data, err = _ask(args.api_url, q, args.top_k, args.temperature)
        ts = datetime.utcnow().isoformat()
        if data is not None and err is None:
            results.append(QAResult(
                id=qid,
                question=q,
                answer=data.get("answer"),
                sources=data.get("sources"),
                context_used=data.get("context_used"),
                status="ok",
                error=None,
                latency_ms=latency_ms,
                timestamp=ts
            ))
        else:
            results.append(QAResult(
                id=qid,
                question=q,
                answer=None,
                sources=None,
                context_used=None,
                status="error",
                error=err,
                latency_ms=latency_ms,
                timestamp=ts
            ))

    # Save
    if args.format == "csv" or args.output.lower().endswith(".csv"):
        _write_output_csv(args.output, results)
    else:
        _write_output_jsonl(args.output, results)

    print(f"[DONE] Wrote {len(results)} results to {args.output}")

if __name__ == "__main__":
    main()
