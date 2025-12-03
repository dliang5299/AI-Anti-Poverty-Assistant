#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from tests.evaluation import evaluate_response

from dotenv import load_dotenv
import os
load_dotenv()  # loads .env into environment variables

# -----------------------------
# Defaults
# -----------------------------

today = datetime.today().strftime("%Y-%m-%d")
OUTPUT_FILE = f"tests/{today}_rag_model_responses.csv"
TIMEOUT = 60               # seconds for per-request timeout
RETRIES = 3
BACKOFF_SEC = 2.0          # simple linear backoff (attempt * BACKOFF_SEC)


# -----------------------------
# Helpers: load gold dataset
# -----------------------------

def load_questions_from_gold(
    csv_path: str = "tests/gold_dataset.csv",
) -> tuple[List[str], Dict[str, str], pd.DataFrame]:
    """
    Load questions and gold annotations from gold_dataset.csv.

    Returns:
        user_prompts: list of unique user_question strings (non-empty)
        id_map: mapping from user_question -> id
        gold_by_id: DataFrame indexed by id so we can look up gold_context/response
    """
    df_input = pd.read_csv(csv_path)
    prompts_df = df_input.drop_duplicates(subset=["user_question"], keep="first")
    user_prompts = prompts_df["user_question"].dropna().tolist()
    id_map = dict(zip(prompts_df["user_question"], prompts_df["id"]))
    gold_by_id = df_input.set_index("id")
    return user_prompts, id_map, gold_by_id


# -----------------------------
# HTTP helpers
# -----------------------------

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


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--api-url",
        required=True,
        help="Base URL for RAG service (e.g., http://localhost:8000)",
    )
    p.add_argument(
        "--gold-csv",
        default="tests/gold_dataset.csv",
        help="Path to gold_dataset.csv (default: tests/gold_dataset.csv)",
    )
    p.add_argument("--ingest-bucket", help="Optional S3 bucket to ingest before asking questions")
    p.add_argument("--ingest-prefix", default="", help="Optional S3 prefix for ingestion")
    p.add_argument("--situation", help="Optional situation string sent to /chat")
    p.add_argument("--with-history", action="store_true", help="Accumulate conversation_history across questions")

    args = p.parse_args()

    try:
        questions, id_map, gold_by_id = load_questions_from_gold(args.gold_csv)
    except Exception as e:
        print(f"[ERROR] Failed to load gold dataset '{args.gold_csv}': {e}", file=sys.stderr)
        sys.exit(2)

    if args.ingest_bucket:
        ok, msg = call_ingest(args.api_url, args.ingest_bucket, args.ingest_prefix)
        print("[INGEST]", "ok" if ok else f"ERROR: {msg}")

    rows: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []

    for i, q in enumerate(questions, start=1):
        qid = id_map.get(q, f"Q{i:03d}")
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
            answer = data.get("response") or ""
            retrieved_texts = data.get("sources") or []
            sources = retrieved_texts
            programs = data.get("programs") or []
            # Try to capture the retrieved context if the API returns it or if sources include text
            retrieved_context = ""
            raw_context = data.get("context") or data.get("retrieved_context")
            if raw_context:
                if isinstance(raw_context, list):
                    retrieved_context = "\n\n".join(str(c) for c in raw_context if c)
                else:
                    retrieved_context = str(raw_context)
            else:
                chunk_texts: List[str] = []
                for s in sources:
                    if not isinstance(s, dict):
                        continue
                    txt = s.get("text") or s.get("content")
                    if txt:
                        chunk_texts.append(str(txt))
                if chunk_texts:
                    retrieved_context = "\n\n".join(chunk_texts)

            # optionally build history for the next turn
            if args.with_history:
                history.append(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": q}],
                    }
                )
                history.append(
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": answer}],
                    }
                )

            # Extract just the URLs from each source dict
            urls: List[str] = []
            for s in sources:
                if not isinstance(s, dict):
                    continue
                u = s.get("source_url") or s.get("url")
                if u:
                    urls.append(u)

            # Look up gold context/response for evaluation
            gold_context = ""
            gold_response = ""
            if qid in gold_by_id.index:
                gold_row = gold_by_id.loc[qid]
                gold_context = str(gold_row.get("gold_context", "") or "")
                gold_response = str(gold_row.get("gold_response", "") or "")

            eval_metrics = evaluate_response(
                user_prompt=q,
                model_answer=answer,
                gold_context=gold_context,
                gold_response=gold_response,
                retrieved_context=retrieved_context,
            )

            row: Dict[str, Any] = {
                "id": qid,
                "question": q,
                "answer": answer,
                "source_urls": json.dumps(urls, ensure_ascii=False),
                "programs_json": json.dumps(programs, ensure_ascii=False),
                "retrieved_context": retrieved_context,
                "status": "ok",
                "error": "",
                "latency_ms": latency,
                "timestamp": ts,
            }
            if isinstance(eval_metrics, dict):
                row.update(eval_metrics)

            rows.append(row)
        else:
            # Error case: record minimal row, leave metrics empty
            row: Dict[str, Any] = {
                "id": qid,
                "question": q,
                "answer": "",
                "source_urls": json.dumps([], ensure_ascii=False),
                "programs_json": json.dumps([], ensure_ascii=False),
                "retrieved_context": "",
                "status": "error",
                "error": err or "unknown error",
                "latency_ms": latency,
                "timestamp": ts,
            }
            rows.append(row)

    if not rows:
        print("[WARN] No questions were processed; nothing to write.")
        return

    # Use keys from first row as columns; later rows may add more keys (e.g. metrics)
    fieldnames: List[str] = list(rows[0].keys())
    # Ensure metric columns from later rows are also included
    for r in rows[1:]:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"✅ DONE → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
