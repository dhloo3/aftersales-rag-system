"""Run a small, reproducible source-grounded QA smoke check against the local app."""

import json
import os
import pathlib
import time
import urllib.request
from datetime import date


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = os.environ.get("AFTERSALES_BASE_URL", "http://127.0.0.1:6039").rstrip("/")
CLIENT_ID = "e5cd7e4891bf95d1d19206ce24a7b32e"
KNOWLEDGE_ID = 2091000000000000100
CASES = [
    {"question": "AX-200 故障排查 SOP 中 E17 的处理顺序是什么", "source": "AX-200-故障排查SOP.md", "terms": ["断电", "散热", "售后工程师", "[1]"]},
    {"question": "AX-200 用户手册规定进气滤芯多久检查一次", "source": "AX-200-用户手册.md", "terms": ["500", "进气滤芯", "[1]"]},
    {"question": "AX-200 的 DEMO-AX200-001 上次 E17 怎么处理的，这能用于所有设备吗", "source": "AX-200-服务记录.md", "terms": ["遮挡", "其他设备", "[1]"]},
    {"question": "AX-200 出现 E42 后怎么办", "source": None, "terms": ["未收录", "售后工程师"]},
]


def post(path, body, token=None):
    headers = {"Content-Type": "application/json", "clientid": CLIENT_ID}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, json.dumps(body, ensure_ascii=False).encode(), headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    login = post("/auth/login", {"clientId": CLIENT_ID, "grantType": "password", "tenantId": "000000", "username": os.environ.get("AFTERSALES_USER", "admin"), "password": os.environ.get("AFTERSALES_PASSWORD", "admin123")})
    token = login["data"]["access_token"]
    results = []
    for case in CASES:
        started = time.perf_counter()
        response = post("/system/aftersales/ask", {"knowledgeId": KNOWLEDGE_ID, "question": case["question"], "topK": 3}, token)
        data = response.get("data", response)
        answer = data.get("answer") or ""
        sources = [source["sourceName"] for source in data.get("sources", [])]
        expected_status = "GENERATED" if case["source"] else "NO_EVIDENCE"
        checks = {
            "status": data.get("status") == expected_status,
            "source": case["source"] in sources if case["source"] else not sources,
            "answerTerms": all(term in answer for term in case["terms"]),
        }
        results.append({"question": case["question"], "status": data.get("status"), "sources": sources, "latencyMs": round((time.perf_counter() - started) * 1000, 2), "checks": checks, "answer": answer})
    report = {"date": str(date.today()), "scope": "4 synthetic AX-200 cases; rule-based smoke checks, not human-rated answer accuracy", "model": "deepseek-flash", "cases": results, "passed": sum(all(row["checks"].values()) for row in results), "total": len(results)}
    output = ROOT / "docs/aftersales-demo/qa-evaluation-latest.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QA smoke checks: {report['passed']}/{report['total']}; report: {output}")
    for row in results:
        print(row["status"], row["checks"], row["latencyMs"])


if __name__ == "__main__":
    main()
