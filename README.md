# 客服 Agent（手搓版）

这是一个客服机器人，用来解决用户一些需求，包括售后和查询等等，可以帮人工减掉一些工作量。

全程手搓，不依赖 LangChain 等 Agent 框架——function calling、记忆系统、RAG 检索均为自己实现。

## 功能特性

- **订单查询**：按订单号查物流状态与配送地址（MySQL 真查库）
- **修改地址 / 修改订单状态**：工具真写库，订单不存在会如实告知
- **退款申请**：一键提交退款
- **优惠券查询**：真查库，没有就说没有
- **转人工工单**：用户问题真落库（tickets 表），人工客服可捞取处理
- **政策问答（RAG）**：embedding + 向量库语义检索，知识库外的问题拒答不瞎编
- **多轮 + 跨会话记忆**：关程序重开，对话不丢
- **网页界面**：Streamlit 聊天 UI，终端版/网页版共用同一大脑

## 技术栈

- Python
- OpenAI SDK（兼容接口：DeepSeek chat 负责对话，硅基流动 BAAI/bge-m3 负责向量化）
- MySQL + PyMySQL（业务数据：订单 / 优惠券 / 工单）
- ChromaDB（向量库，余弦近邻检索）
- Streamlit（网页界面）
- numpy（余弦相似度计算）

## 项目结构

| 文件 | 职责 |
| --- | --- |
| main.py | 主流程 + answer() 两轮调用循环 |
| tools.py | 工具三件套：Schema 说明书 / 函数真身 / execute 注册 |
| db.py | MySQL 访问层（订单、优惠券、工单） |
| Memory.py | 跨会话记忆（load / persist） |
| LLM.py | DeepSeek 聊天封装 |
| embedding.py | bge-m3 向量化封装 + cosine 相似度 |
| knowledge.py | 政策知识库 + ChromaDB 集合管理 |
| app.py | Streamlit 网页入口 |
| vector_db.py | 向量库实验脚本 |

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置密钥：复制 `.env.example` 为 `.env`，填入 `DEEPSEEK_API_KEY`、`SILICONFLOW_API_KEY` 及 MySQL 连接信息；

3. 在 MySQL 中创建 `shop` 库，并建三张表：`orders`（订单号/状态/地址）、`coupons`（用户优惠券）、`tickets`（转人工工单）；

4. 启动网页版：

```bash
streamlit run app.py
```

（终端版：`python main.py`）

## 工作原理

**对话主循环（function calling 两轮法）**

- 第一轮：把对话历史 + 工具说明书发给模型，让它决定「要不要调用工具、调用哪个」；
- 模型喊了工具 → 执行，结果以 `role="tool"` 回填（带 `tool_call_id` 与调用配对）；
- 第二轮：不带工具再问一次模型，让它根据工具结果组织成对用户的话术。

**RAG 检索（检索 → 增强 → 生成）**

- 知识库政策文档用 bge-m3 向量化，存入 ChromaDB；
- 用户问题同样向量化，余弦近邻检索最相关政策（距离阈值 0.9，实测标定）；
- 检索结果作为工具结果回填给模型，模型据此作答——知道的说，不知道的不编。

**记忆**

- 每轮对话持久化到 memory.json，启动时读回；关程序重开，模型还记得你是谁。
