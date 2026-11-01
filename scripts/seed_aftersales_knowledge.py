"""Seed the synthetic AX-200 corpus into the app's MySQL and Weaviate stores.

Reads API credentials from ignored .env.local. Requires the local Docker services.
"""

import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ID = 2091000000000000100
CLASS_NAME = f"LocalKnowledge{KNOWLEDGE_ID}"
WEAVIATE = "http://127.0.0.1:28080/v1"
EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
secrets = dict(line.split("=", 1) for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines() if "=" in line)


def request(url, body=None, headers=None, method=None):
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def quote(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


docs = sorted((ROOT / "docs/aftersales-demo/knowledge").glob("*.md"))
if len(docs) != 3:
    raise SystemExit("Expected the three AX-200 Markdown documents")

segments = []
for doc in docs:
    content = doc.read_text(encoding="utf-8").strip()
    doc_id = hashlib.md5(doc.name.encode("utf-8")).hexdigest()
    fid = hashlib.md5((doc.name + content).encode("utf-8")).hexdigest()
    segments.append({"name": doc.name, "text": content, "docId": doc_id, "fid": fid})

start = time.perf_counter()
response = request(EMBEDDING_URL,
                   {"model": "qwen3-vl-embedding",
                    "input": {"contents": [{"text": item["text"]} for item in segments]},
                    "parameters": {"dimension": 1024}},
                   {"Authorization": "Bearer " + secrets["DASHSCOPE_API_KEY"]})
items = sorted(response["output"]["embeddings"], key=lambda item: item["index"])
if len(items) != len(segments) or any(len(item["embedding"]) != 1024 for item in items):
    raise RuntimeError("Embedding count or dimension mismatch")
embedding_ms = (time.perf_counter() - start) * 1000

schema = request(WEAVIATE + "/schema")
if CLASS_NAME not in {item["class"] for item in schema.get("classes", [])}:
    request(WEAVIATE + "/schema", {"class": CLASS_NAME, "vectorizer": "none",
            "properties": [{"name": name, "dataType": ["text"]}
                           for name in ("text", "fid", "kid", "docId")]})

objects = []
for item, vector_item in zip(segments, items):
    vector = vector_item["embedding"]
    norm = math.sqrt(sum(value * value for value in vector))
    objects.append({"class": CLASS_NAME,
                    "id": str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_DNS, item["fid"])),
                    "properties": {"text": item["text"], "fid": item["fid"],
                                   "kid": str(KNOWLEDGE_ID), "docId": item["docId"]},
                    "vector": [value / norm for value in vector]})
batch = request(WEAVIATE + "/batch/objects", {"objects": objects})
errors = [item for item in batch if item.get("result", {}).get("errors")]
if errors:
    raise RuntimeError("Weaviate batch insert failed")

sql = [f"DELETE FROM knowledge_fragment WHERE knowledge_id={KNOWLEDGE_ID};",
       f"DELETE FROM knowledge_attach WHERE knowledge_id={KNOWLEDGE_ID};",
       f"DELETE FROM knowledge_info WHERE id={KNOWLEDGE_ID};",
       "INSERT INTO knowledge_info (id,user_id,name,share,description,retrieve_limit,similarity_threshold,"
       "text_block_size,vector_model,embedding_model,tenant_id,enable_hybrid,hybrid_alpha) VALUES ("
       f"{KNOWLEDGE_ID},1,'AX-200 售后知识库',1,'虚构设备演示资料',3,0,2000,'weaviate','qwen3-vl-embedding',0,1,0.5);" ]
for item in segments:
    sql.append("INSERT INTO knowledge_attach (knowledge_id,doc_id,file_hash,name,type,tenant_id,status) VALUES ("
               f"{KNOWLEDGE_ID},{quote(item['docId'])},{quote(hashlib.sha256(item['text'].encode()).hexdigest())},"
               f"{quote(item['name'])},'md',0,2);")
    sql.append("INSERT INTO knowledge_fragment (fid,idx,doc_id,content,knowledge_id,tenant_id) VALUES ("
               f"{quote(item['fid'])},0,{quote(item['docId'])},{quote(item['text'])},{KNOWLEDGE_ID},0);")
subprocess.run(["docker", "exec", "-i", "aftersales-demo-mysql-1", "mysql", "-uroot", "-proot",
                "--default-character-set=utf8mb4", "-D", "ruoyi-ai"],
               input="\n".join(sql).encode("utf-8"), stdout=subprocess.DEVNULL, check=True)
print(json.dumps({"knowledgeId": KNOWLEDGE_ID, "documents": len(segments), "fragments": len(segments),
                  "dimensions": 1024, "embeddingBatchMs": round(embedding_ms, 2)}, ensure_ascii=False))
