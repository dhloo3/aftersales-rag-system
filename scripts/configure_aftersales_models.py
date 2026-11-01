"""Install local demo model records without putting API keys in versioned SQL."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines()
    if line and not line.startswith("#") and "=" in line
)


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


deepseek = sql_string(values["DEEPSEEK_API_KEY"])
dashscope = sql_string(values["DASHSCOPE_API_KEY"])
sql = f"""
INSERT INTO chat_provider (id, provider_name, provider_code, api_host, status, tenant_id)
VALUES (2091000000000000003, '百炼多模态向量', 'bailianMultiModel',
        'https://dashscope.aliyuncs.com', '0', 0)
ON DUPLICATE KEY UPDATE status='0', api_host=VALUES(api_host);
INSERT INTO chat_model
  (id, category, sort_order, model_name, provider_code, model_describe,
   model_show, api_host, api_key, tenant_id)
VALUES
  (2091000000000000001, 'chat', 1, 'deepseek-flash', 'deepseek',
   'AX-200 售后溯源问答', 'Y', 'https://api.deepseek.com', {deepseek}, 0),
  (2091000000000000002, 'vector', 1, 'qwen3-vl-embedding', 'bailianMultiModel',
   'AX-200 1024 维多模态向量', 'Y',
   'https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding',
   {dashscope}, 0)
ON DUPLICATE KEY UPDATE
  model_name=VALUES(model_name), provider_code=VALUES(provider_code),
  api_host=VALUES(api_host), api_key=VALUES(api_key), model_show=VALUES(model_show);
UPDATE chat_model SET model_dimension=1024 WHERE id=2091000000000000002;
"""
subprocess.run(
    ["docker", "exec", "-i", "aftersales-demo-mysql-1", "mysql", "-uroot", "-proot",
     "--default-character-set=utf8mb4", "-D", "ruoyi-ai"],
    input=sql.encode("utf-8"),
    stdout=subprocess.DEVNULL,
    check=True,
)
print("Configured DeepSeek chat and DashScope 1024-dimensional embedding models.")
