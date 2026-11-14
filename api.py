"""FastAPI 版客服接口。

身份怎么确认：先 POST /login 换一张令牌（token），
之后每次请求都带上请求头  Authorization: Bearer <令牌>。
服务器从令牌里解出 user_id —— 客户端自己报的编号一律不认。
"""
import asyncio
import json
import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import Memory
import main
import graph
import db
import auth
import knowledge
import 限流
from LLM import 累计用量

logger = logging.getLogger(__name__)

app = FastAPI(
    title="客服 Agent API",
    description=(
        "登录拿令牌 → 之后每个业务接口都带 `Authorization: Bearer <令牌>`。\n\n"
        "对话有普通 JSON（`/chat`）和流式 SSE（`/chat/stream`）两种。"
    ),
    version="1.0.0",
)


# ============ 请求体 / 响应体模板（FastAPI 按它自动校验） ============
class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=64)


class ChatRequest(BaseModel):
    """注意：没有 user_id 了 —— 你是谁由令牌说了算，不是由请求体说了算。"""
    message: str = Field(min_length=1, max_length=500)  # 必传，且 1~500 字


class ChatResponse(BaseModel):
    reply: str


class TokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    user_id: str
    messages: list[HistoryMessage]


# ============ 身份校验（依赖注入） ============
def 当前用户(authorization: str | None = Header(default=None)):
    """从请求头里取令牌、验令牌、返回 user_id。

    FastAPI 的 Depends 会先跑这个函数：验不过就 401，接口本体压根不会被调用。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="请先登录（请求头格式：Authorization: Bearer <令牌>）",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return auth.验证令牌(authorization[7:])
    except auth.令牌无效 as e:
        raise HTTPException(
            status_code=401,
            detail=f"{e}，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )


# 管家表：user_id → 管家（模块级字典，进程活着就在）
管家表 = {}


def 找管家(user_id):
    """给每个用户发一个独立管家（记忆文件按编号分家）。"""
    if user_id not in 管家表:
        m = Memory.Memory(path=f"memory_{user_id}.json", user_id=user_id)
        m.load()
        管家表[user_id] = m
    return 管家表[user_id]


# ============ 注册 / 登录 ============
@app.post("/register", tags=["认证"])
def 注册(请求: LoginRequest):
    """注册新账号。409 = 账号已存在。"""
    try:
        auth.注册(请求.user_id, 请求.password)
    except auth.登录失败 as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"user_id": 请求.user_id, "msg": "注册成功，请登录"}


@app.post("/login", response_model=TokenResponse, tags=["认证"])
def 登录(请求: LoginRequest):
    """账号密码换令牌。401 = 账号或密码不对，429 = 试得太频繁。"""
    # 防暴力猜密码：同一个账号每分钟最多试 5 次
    键 = "login:" + 请求.user_id
    if not 限流.允许(键, 上限=限流.登录每分钟上限):
        等 = 限流.建议等待秒数(键)
        raise HTTPException(
            status_code=429,
            detail=f"尝试太频繁，请 {等} 秒后再试",
            headers={"Retry-After": str(等)},
        )

    try:
        token = auth.登录(请求.user_id, 请求.password)
    except auth.登录失败 as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {
        "token": token,
        "token_type": "Bearer",
        "expires_in": auth.令牌有效秒数,
        "user_id": 请求.user_id,
    }


# ============ 基础接口 ============
@app.get("/hello", tags=["运维"])
def 你好():
    return {"msg": "你好，世界"}


@app.get("/health", tags=["运维"])
def 健康检查():
    """给运维/负载均衡探活用：依赖挂了就返回 503，别把坏实例留在线上。

    注意：探活接口不能要求登录 —— 负载均衡器手里没有令牌。
    """
    try:
        db.get_order("__health_check__")     # 只证明"连得上、查得动"，不关心查没查到
    except Exception:
        logger.exception("健康检查失败：数据库连不上")
        raise HTTPException(status_code=503, detail="数据库连不上")
    return {
        "status": "ok",
        "db": "ok",
        "知识库条数": knowledge.collection.count(),
    }


@app.get("/stats", dependencies=[Depends(当前用户)], tags=["运维"])
def 用量统计():
    """看一眼这个进程启动以来烧了多少 token（成本控制的第一步：先看得见）。

    token 用量算经营数据，不能让外面的人随便看，所以也要登录。
    """
    return {
        "累计用量": 累计用量,
        "知识库条数": knowledge.collection.count(),
    }


@app.get("/orders/{order_id}", tags=["订单"])
def 查订单(order_id: str, user_id: str = Depends(当前用户)):
    """订单查询接口：不经过大模型，直接查库。

    别人的单也返回 404 —— 不让人靠试订单号摸出"哪些单真实存在"。
    """
    订单 = db.get_order(order_id)          # 同步 IO，写成普通 def，FastAPI 自动扔线程池
    if not 订单 or 订单.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return 订单


async def 流式生成器(q):
    """异步生成器：模型吐一片，就 yield 一片（函数不结束，下次接着跑）。"""
    async for chunk in main.llm.astream([{"role": "user", "content": q}]):
        if not chunk.choices:                    # 最后一片只带 usage，没有正文
            continue
        小片 = chunk.choices[0].delta.content    # 流式给的是 delta（增量）
        if 小片:                                  # 首尾 chunk 的 content 通常是 None
            yield 小片


@app.get("/stream_demo", dependencies=[Depends(当前用户)], tags=["对话"])
async def stream_demo(q: str = "你好"):
    """流式演示：登录后浏览器打开就能看到字一个个蹦出来。

    为什么要登录：这个接口每调一次都真烧 API 额度，
    不设防等于把钱包挂在网上。
    """
    return StreamingResponse(流式生成器(q), media_type="text/plain")


@app.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(请求: ChatRequest, user_id: str = Depends(当前用户)):
    """API 版客服：带令牌进来，收 JSON(message)，回 JSON(reply)。"""
    q = 请求.message.strip()
    if not q:
        raise HTTPException(status_code=400, detail="message 不能为空")

    # 限流：key 用令牌里解出的 user_id，换号刷不动了
    if not 限流.允许(user_id):
        等 = 限流.建议等待秒数(user_id)
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁啦，请 {等} 秒后再试",
            headers={"Retry-After": str(等)},
        )

    # 找管家要读记忆文件：同步 IO 扔进线程，避免卡住事件循环
    # 管家从参数一路传下去，不再写全局 main.memory —— 两个请求同时进来也不会串号
    管家 = await asyncio.to_thread(找管家, user_id)
    reply = await graph.answer_async(管家, q)   # LangGraph 版大脑
    return {"reply": reply}                     # 客服的话包成 JSON 发回


@app.post("/chat/stream", tags=["对话"])
async def chat_stream(请求: ChatRequest, user_id: str = Depends(当前用户)):
    """流式版客服：SSE 协议，一行一条 data，最后一条是 [DONE]。

    和普通 /chat 的区别只有一个：边生成边发，用户不用等整段说完。
    """
    q = 请求.message.strip()
    if not q:
        raise HTTPException(status_code=400, detail="message 不能为空")

    if not 限流.允许(user_id):
        等 = 限流.建议等待秒数(user_id)
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁啦，请 {等} 秒后再试",
            headers={"Retry-After": str(等)},
        )

    管家 = await asyncio.to_thread(找管家, user_id)

    async def 事件流():
        try:
            async for 片 in graph.answer_stream_async(管家, q):
                # SSE 的规矩：每条消息以 "data: " 开头，空行结尾。
                # 包成 JSON 是为了把换行、引号安全地转义掉。
                yield f"data: {json.dumps({'text': 片}, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("流式接口出错")
            yield f"data: {json.dumps({'error': '系统开小差了，请稍后再试'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"        # 结束标记：告诉客户端别等了

    return StreamingResponse(
        事件流(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 告诉 Nginx 别攒着，来一片转一片
        },
    )


# ============ 对话历史 ============
def _可见历史(管家):
    """只给聊天界面能看懂的：用户说的话和客服的回复。

    system（人设/摘要）和 tool（工具原始输出）是给模型看的，不往外暴露。
    """
    return [
        {"role": m["role"], "content": m["content"]}
        for m in 管家.messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


@app.get("/history", response_model=HistoryResponse, tags=["对话"])
def 查历史(user_id: str = Depends(当前用户)):
    """这个用户到目前为止的对话记录（不含 system 和工具内部消息）。"""
    管家 = 找管家(user_id)       # 普通 def，FastAPI 自动扔线程池，不会卡事件循环
    return {"user_id": user_id, "messages": _可见历史(管家)}


@app.delete("/history", tags=["对话"])
def 清空历史(user_id: str = Depends(当前用户)):
    """清空这个用户的对话记忆。只清聊天记录，订单/优惠券不受影响。"""
    管家 = 找管家(user_id)
    管家.messages.clear()
    管家.persist()
    return {"msg": "对话历史已清空", "user_id": user_id}
