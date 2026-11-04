from fastapi import FastAPI
import Memory
import main

app = FastAPI()

# 管家表：user_id → 管家（模块级字典，进程活着就在）
管家表 = {}


def 找管家(user_id):
    """给每个用户发一个独立管家（记忆文件按编号分家）。"""
    if user_id not in 管家表:
        m = Memory.Memory(path=f"memory_{user_id}.json")
        m.load()
        管家表[user_id] = m
    return 管家表[user_id]


@app.get("/hello")
def 你好():
    return {"msg": "你好，世界"}


@app.post("/chat")
def chat(请求: dict):
    """API 版客服：收 JSON（user_id + message），回 JSON（reply）。"""
    user_id = 请求.get("user_id", "guest")
    q = 请求.get("message", "")
    if not q:
        return {"reply": "请提供 message"}

    main.memory = 找管家(user_id)                  # 换管家：每人一份记忆
    reply = main.answer(main.memory.messages, q)   # 把消息交给大脑
    return {"reply": reply}                        # 客服的话包成 JSON 发回
