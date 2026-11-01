"""Measure retrieval latency and document Recall@K against a running instance.

Usage: python scripts/evaluate_aftersales_retrieval.py --base-url http://localhost:8080
       --knowledge-id 123 --token TOKEN --questions docs/aftersales-demo/questions.jsonl
"""
import argparse
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * p) - 1)]


def evaluate(args):
    questions = [json.loads(line) for line in Path(args.questions).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not questions:
        raise ValueError("questions file is empty")
    latencies = []
    labelled = 0
    hits = 0
    failures = 0
    details = []
    for item in questions:
        body = json.dumps({
            "knowledgeId": args.knowledge_id,
            "query": item["query"],
            "topK": args.top_k,
            "enableHybrid": args.hybrid,
            "hybridAlpha": getattr(args, "hybrid_alpha", None),
            "enableRerank": args.rerank,
        }).encode("utf-8")
        request = urllib.request.Request(
            args.base_url.rstrip("/") + "/system/fragment/retrieval",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + args.token,
                     "clientid": args.client_id},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                payload = json.load(response)
            if payload.get("code") != 200:
                raise ValueError(f"API returned code={payload.get('code')}: {payload.get('msg')}")
            results = payload.get("data") or []
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies.append(elapsed_ms)
            sources = {result.get("sourceName") for result in results[:args.top_k]}
            expected = set(item.get("expectedSourceNames") or [])
            hit = bool(expected & sources) if expected else None
            if hit is not None:
                labelled += 1
                hits += int(hit)
            details.append({"query": item["query"], "latencyMs": round(elapsed_ms, 2),
                            "sourceNames": sorted(name for name in sources if name), "hit": hit})
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            failures += 1
            details.append({"query": item["query"], "error": str(error)})

    report = {
        "total": len(questions), "success": len(latencies), "failures": failures,
        "topK": args.top_k, "labelled": labelled,
        "documentRecallAtK": round(hits / labelled, 4) if labelled else None,
        "p50Ms": round(percentile(latencies, 0.5), 2) if latencies else None,
        "p95Ms": round(percentile(latencies, 0.95), 2) if latencies else None,
        "details": details,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--knowledge-id", required=True, type=int)
    parser.add_argument("--token", required=True)
    parser.add_argument("--client-id", default="e5cd7e4891bf95d1d19206ce24a7b32e")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--hybrid-alpha", type=float, default=0.3)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--timeout", type=float, default=15)
    evaluate(parser.parse_args())
