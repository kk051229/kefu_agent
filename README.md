# 客服 Agent（手搓版）

这是一个客服机器人，用来解决用户一些需求，包括售后和查询等等，可以帮人工减掉一些工作量。

function calling、记忆系统、RAG 检索均为自己实现；主流程已迁移到 LangGraph，用状态图管理「问模型 → 调工具 → 组织话术」。

## 功能特性

- **登录鉴权**：注册 / 登录换 JWT 令牌；密码存 PBKDF2 加盐哈希，不存明文
- **订单归属校验**：订单查询、改地址、改状态、退款都校验"这单是不是你的"，别人的单一律查不到、改不动
- **订单查询**：按订单号查物流状态与配送地址（MySQL 真查库）
- **修改地址 / 修改订单状态**：工具真写库，订单不存在会如实告知
- **退款申请**：一键提交退款
- **优惠券查询**：真查库，没有就说没有
- **转人工工单**：用户问题真落库（tickets 表），人工客服可捞取处理
- **政策问答（RAG）**：20 条短政策 + 长文档切块，向量检索 top-3，域外问题拒答不瞎编
- **多轮 + 跨会话记忆**：按用户分文件存储，超长对话自动摘要；关程序重开，对话不丢
- **三种形态**：终端 / Streamlit 网页 / FastAPI 接口，共用同一套大脑
- **流式对话**：`POST /chat/stream`（SSE）边生成边返回；`/stream_demo` 是纯模型演示
- **网页流式**：Streamlit 聊天页边生成边显示（`st.write_stream` + 线程桥接异步生成器）

## 技术栈

- Python
- 标准库手搓 JWT（HS256）+ PBKDF2 密码哈希，不依赖第三方鉴权库
- OpenAI SDK（兼容接口：DeepSeek chat 负责对话，硅基流动 BAAI/bge-m3 负责向量化）
- MySQL + PyMySQL（业务数据：订单 / 优惠券 / 工单）
- ChromaDB（向量库，余弦近邻检索）
- LangGraph（主流程状态图）
- FastAPI + uvicorn（HTTP 接口、异步、流式）
- Streamlit（网页界面）
- pytest（单元测试）

## 项目结构

| 文件 | 职责 |
| --- | --- |
| graph.py | LangGraph 版主流程：ask → execute_tools → answer → 收尾 |
| main.py | 手写版两轮循环（对照实现）+ 人设、理发、日志 |
| auth.py | 登录：PBKDF2 密码哈希 + JWT 签发/验证（HS256 手搓版） |
| tools.py | 工具三件套：Schema 说明书 / 函数真身 / execute 注册 |
| db.py | MySQL 访问层（订单、优惠券、工单） |
| Memory.py | 跨会话记忆（load / persist） |
| LLM.py | DeepSeek 聊天封装 + token 用量统计 |
| llm_base.py | 模型客户端父类（同步/异步客户端按事件循环发放） |
| embedding.py | bge-m3 向量化封装 + cosine 相似度 |
| knowledge.py | 政策知识库 + 长文档切块 + ChromaDB 集合管理 |
| chunking.py | 长文档切块（按段落、按句、标题绑定、重叠） |
| rag_eval.py | RAG 评测集（34 题）+ 阈值扫描 |
| api.py | FastAPI 入口（/login、/register、/chat、/chat/stream、/health、/stats、/stream_demo） |
| app.py | Streamlit 网页入口（先登录再聊天，回复流式显示） |
| 限流.py | 按用户的滑动窗口限流 |
| migrate_auth.py | 给老数据库补 users 表 / orders.user_id（幂等，不动数据） |
| tests/ | pytest 单元测试（63 条） |

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements-dev.txt   # 含生产依赖 + pytest
```

2. 配置密钥：复制 `.env.example` 为 `.env`，填入 `DEEPSEEK_API_KEY`、`SILICONFLOW_API_KEY`、MySQL 连接信息，以及 `JWT_SECRET`（一串随机字符）：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

3. 初始化数据库：

```bash
mysql -u root -p < schema.sql     # 新库：建表 + 演示数据（会先删后插）
python migrate_auth.py            # 老库：只补 users 表 / user_id 列，不动数据
```

4. 启动（三选一，都要先登录，演示账号 `u001` / `u002`，密码 `123456`）：

```bash
python main.py                          # 终端版
streamlit run app.py                    # 网页版
uvicorn api:app --reload --port 8000    # API 版，文档在 http://127.0.0.1:8000/docs
```

5. 跑测试：

```bash
pytest
```

6. API 调用示例（先登录换令牌，再带令牌聊天）：

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u001","password":"123456"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -X POST http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我查订单 kx666"}'
```

流式版（`-N` 关掉 curl 的缓冲，才能看到字一片片到达）：

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我查订单 kx666"}'
```

## 部署

```bash
docker compose up -d --build     # 拉起 MySQL + API，自动执行 schema.sql
curl http://localhost:8000/health
```

## 工作原理

**对话主流程（LangGraph 状态图）**

```
ask ──有工具──→ execute_tools ──→ answer ──┐
 │  └─没工具─→ direct ────────────────────┴─→ 收尾 ──→ END
 └─第一轮就报错────────────────────────────→ 收尾
```

- `ask`：把对话历史 + 工具说明书发给模型，让它决定「要不要调用工具、调用哪个」；
- `execute_tools`：执行工具，结果以 `role="tool"` 回填（带 `tool_call_id` 与调用配对）；
- `answer`：不带工具再问一次模型，把工具结果组织成对用户的话术；
- `收尾`：回填最终回复 → 理发 → 落盘。管家（memory）从参数传入，不用全局变量，多用户并发不串号。

**流式对话（SSE）**

- 第一轮（决定调不调工具）不流；有工具时第二轮 `stream=True`，边生成边转发；
- 每片 `data: {"text": ...}`，结束发 `data: [DONE]`；
- `stream_options={"include_usage": True}` 让流式请求的 token 也进 `/stats`；
- 生成器 `finally` 收尾：写回回复 → 理发 → 落盘，中途断开也不留半截。

**RAG 检索（检索 → 增强 → 生成）**

- 短政策「一条 = 一块」；长文档经 `chunking.py` 切块（约 300 字/块，相邻块重叠 60 字，章节标题与正文绑定）；
- bge-m3 向量化后存 ChromaDB，向量按内容指纹缓存，知识库不变时启动零 API 调用；
- 检索取 top-3：**第 1 名距离 < 0.95 才放行**（`rag_eval.py` 实测标定：域内最差 0.919，域外最近 1.053），其余同样够像的一起拼成资料给模型；
- 检索结果作为工具结果回填，模型据此作答——知道的说，不知道的不编。

**身份与鉴权（登录之后，谁是谁）**

- 密码存 PBKDF2 加盐哈希（20 万次迭代），同一密码每次存出来都不同；验证用定长时间比较；
- 登录成功签发 JWT（HS256 手搓版）：`header.payload.signature` 三段 base64，签名 = HMAC-SHA256(前两段, `JWT_SECRET`)，2 小时过期；
- 每个请求带 `Authorization: Bearer <令牌>`，`当前用户` 依赖验签后拿到 `user_id`，失败返回 401；
- 身份只从令牌来：请求体里的 `user_id` 不看，模型参数里的 `user_id` 也丢掉；
- 越权防护两层：工具先查归属，`UPDATE ... WHERE order_id=? AND user_id=?` 兜底；
- 别人的订单和"不存在"回同一句话，不泄露订单是否真实存在；
- 公开接口只有 `/hello`、`/health`、`/login`、`/register`（探活不能要令牌，其余连 `/stats` 和 `/stream_demo` 都要登录）。

**记忆**

- 每个用户一个 `memory_{user_id}.json`，启动时读回；超过 40 条自动把老消息压缩成摘要。

**工程化**

- 69 条 pytest 单测：工具分支与越权、图四条路径（含异常）、流式路径、HTTP 校验、登录/令牌、限流、切块器；
- `/health` 探活（数据库不通返回 503）、`/stats` 看累计 token 用量；
- 限流：聊天每用户每分钟 10 次，登录每账号每分钟 5 次（防暴力猜密码），超限返回 429 + `Retry-After`；
- 日志：异常只进日志，用户只看到兜底话术。
