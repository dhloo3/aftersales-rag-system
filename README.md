# 企业设备售后知识检索与溯源问答系统

基于 [RuoYi AI](https://github.com/ageerle/ruoyi-ai) 的后端二次开发，面向设备手册、故障排查 SOP 和历史维修记录的检索与问答。项目是 Java 多模块应用，包含随 Spring Boot 一起运行的售后工作台前端。页面专注售后场景。

## 功能与代码

| 功能 | 入口与实现 |
| --- | --- |
| 文档上传、去重、异步解析和重试 | `modules/rag` 中的 `KnowledgeAttachController`、`KnowledgeAttachServiceImpl` |
| PDF、Word、Excel、Markdown 解析 | `modules/rag` 中的资源加载器与解析器 |
| MySQL 全文检索、向量检索、RRF 融合及可选重排 | `KnowledgeRetrievalServiceImpl`、`VectorStoreStrategyFactory` |
| 售后问答与来源片段返回 | `AftersalesQaController`，`POST /system/aftersales/ask` |
| 登录态、权限、基础系统数据 | `app`、`modules/system`、`common` |
| 售后工作台前端 | `app/src/main/resources/static/aftersales` |

向量存储策略支持 Weaviate、Milvus、Qdrant；本地演示使用 Weaviate。售后 `/ask` 是同步 JSON 接口，返回回答、文档名、文档 ID、片段 ID 和分数。通用聊天的 SSE 能力来自基础平台。

- `app`：Spring Boot 启动模块、配置及售后工作台页面。
- `modules/rag`：知识库、检索、模型调用和售后问答。
- `modules/system`：用户、角色、权限和系统管理。
- `common`：上述模块使用的公共组件。
- `docs/aftersales-demo`：虚构 AX-200 资料、Docker Compose 和复测记录。
- `docs/script/sql`：初始化 SQL 和知识库索引迁移。
- `scripts`：本地模型配置、样例数据装载和评测脚本。

Maven artifactId 和 Java 包名沿用上游项目，以保留多模块依赖关系；目录名按本项目用途整理。

## 本地运行

需要 JDK 17、Maven 3.9+、Python 3.10+ 和 Docker Desktop。DeepSeek 与百炼 API Key 由使用者自行申请，不能写入仓库。以下命令在项目根目录的 PowerShell 执行。

```powershell
Copy-Item .env.example .env.local
# 编辑 .env.local，填写 DEEPSEEK_API_KEY 和 DASHSCOPE_API_KEY

docker compose -f docs/aftersales-demo/docker-compose.local.yml up -d
mvn -pl app -am -DskipTests package
java -jar app/target/ruoyi-admin.jar --spring.profiles.active=dev
```

在另一个 PowerShell 窗口执行：

```powershell
python scripts/configure_aftersales_models.py
python scripts/seed_aftersales_knowledge.py
python scripts/evaluate_aftersales_qa.py
```

启动后打开 `http://127.0.0.1:6039/aftersales/index.html`，登录后可管理知识库、上传资料、查看解析状态、测试检索并进行溯源问答。

本地服务默认使用 `127.0.0.1`：后端 `6039`、MySQL `3306`、Redis `6379`、Weaviate `28080`、MinIO API `9000`、MinIO 控制台 `9090`。Docker Compose 使用演示密码，远程或生产环境需自行更换，并配置 `MYSQL_PASSWORD`、`MINIO_PASSWORD`、`SA_TOKEN_JWT_SECRET` 等环境变量。已有数据库需要运行 `docs/script/sql/update/2026-10-15-knowledge-attach-lookup.sql`；全新数据库由 Compose 导入 `ruoyi-ai.sql`。

样例知识库 ID 是 `2091000000000000100`。请求示例（需先通过 `/auth/login` 取得拥有 `system:fragment:list` 权限的 token）：

```powershell
$headers = @{ Authorization = 'Bearer <TOKEN>'; clientid = 'e5cd7e4891bf95d1d19206ce24a7b32e' }
$body = @{ knowledgeId = 2091000000000000100; question = 'AX-200 出现 E17 后怎么办'; topK = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:6039/system/aftersales/ask' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

没有 API Key 时，MySQL、Redis、Weaviate 等依赖仍可启动；真实 Embedding 装载和模型回答需要对应的 API Key。`scripts/seed_aftersales_knowledge.py` 直接装载演示语料，不经过 MinIO 上传与异步解析；后两项尚未完成本次端到端实测。

