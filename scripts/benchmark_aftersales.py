"""Reproducible local AX-200 retrieval benchmark; no generation score is inferred."""

import argparse
import json
import math
import os
from pathlib import Path
import platform
import time
import urllib.request


CLIENT_ID = "e5cd7e4891bf95d1d19206ce24a7b32e"


def post(url, payload, headers=None):
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response)


def percentile(values, p):
    ordered = sorted(values)
    return round(ordered[math.ceil(len(ordered) * p) - 1], 2) if ordered else None


def main(args):
    base = args.base_url.rstrip("/")
    login = post(base + "/auth/login", {"clientId": CLIENT_ID, "grantType": "password",
        "tenantId": "000000", "username": args.username,
        "password": os.environ.get("AFTERSALES_ADMIN_PASSWORD", "admin123")})
    if login.get("code") != 200:
        raise RuntimeError("Demo admin login failed")
    headers = {"Authorization": "Bearer " + login["data"]["access_token"], "clientid": CLIENT_ID}
    questions = [json.loads(line) for line in Path(args.questions).read_text(encoding="utf-8").splitlines() if line.strip()]

    def retrieve(query, hybrid, nonce=None):
        body = {"knowledgeId": args.knowledge_id, "query": query, "topK": 1,
                "enableHybrid": hybrid, "hybridAlpha": 0.3, "enableRerank": False}
        if nonce is not None:
            body["evaluationRequestId"] = nonce  # ignored by the BO, distinct for RepeatSubmit
        start = time.perf_counter()
        payload = post(base + "/system/fragment/retrieval", body, headers)
        elapsed = (time.perf_counter() - start) * 1000
        if payload.get("code") != 200:
            raise RuntimeError(f"Retrieval API code={payload.get('code')}")
        return payload.get("data") or [], elapsed

    report = {"environment": {"date": time.strftime("%Y-%m-%d"), "os": platform.platform(),
        "corpusDocuments": 3, "fragments": 3, "embeddingModel": "qwen3-vl-embedding",
        "embeddingDimensions": 1024, "vectorStore": "Weaviate 1.30",
        "sample": "synthetic AX-200 knowledge; 30 manually labelled questions"}}
    for name, hybrid in (("vectorCold", False), ("hybridColdAlpha03", True)):
        details, latencies = [], []
        for question in questions:
            hits, elapsed = retrieve(question["query"], hybrid)
            latencies.append(elapsed)
            source = hits[0].get("sourceName") if hits else None
            details.append({"query": question["query"], "expected": question["expectedSourceNames"],
                            "top1Source": source, "hit": source in question["expectedSourceNames"],
                            "latencyMs": round(elapsed, 2)})
        report[name] = {"requests": len(details), "success": len(latencies), "failures": 0,
                        "recallAt1": round(sum(item["hit"] for item in details) / len(details), 4),
                        "p50Ms": percentile(latencies, 0.5), "p95Ms": percentile(latencies, 0.95),
                        "details": details}
        print(name, "Recall@1", report[name]["recallAt1"], "P95 ms", report[name]["p95Ms"], flush=True)

    # Unique, semantically equivalent variants force the embedding/retrieval branch again.
    cold = []
    for i in range(100):
        query = questions[i % len(questions)]["query"] + f"。请依据资料回答（评测变体 {i + 1}）"
        _, elapsed = retrieve(query, True)
        cold.append(elapsed)
    report["uncachedVariants100"] = {"requests": 100, "success": 100, "failures": 0,
        "concurrency": 1, "cache": "100 unique query variants; embedding and retrieval executed",
        "p50Ms": percentile(cold, 0.5), "p95Ms": percentile(cold, 0.95)}
    report["limitations"] = ["RepeatSubmit rejects rapid identical requests, so no warm-cache P95 is reported.",
                             "AX-200 corpus and questions are synthetic; these metrics do not estimate production accuracy."]
    print("uncachedVariants100 P95 ms", report["uncachedVariants100"]["p95Ms"], flush=True)

    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("report:", args.report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:6039")
    parser.add_argument("--knowledge-id", type=int, default=2091000000000000100)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--questions", default="docs/aftersales-demo/questions-30.jsonl")
    parser.add_argument("--report", default="docs/aftersales-demo/evaluation-latest.json")
    main(parser.parse_args())
