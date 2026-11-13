"""LangGraph 版客服大脑：把 main.py 里手写的 answer() 七步翻译成一张图。

为什么要图：手写版是"一条直线 + 两个 if"，流程一复杂（重试、人工介入、
多轮工具、并行分支）就会变成一坨嵌套。图版把每步拆成节点，流程图就是代码。

图结构（和 answer() 一一对应）：
    ask ──有工具──→ execute_tools ──→ answer ──┐
     │  └─没工具─→ direct ────────────────────┴─→ 收尾 ──→ END
     └─第一轮就报错────────────────────────────→ 收尾

和旧版的区别不只是"换个写法"：
1. 管家（memory）从参数进来，不再用全局变量 → 并发请求不会串号；
2. 收尾节点统一做「回填历史 → 理发 → 落盘」，三条路径共用一套收尾逻辑。
"""
import asyncio
import json
from typing import Annotated, TypedDict
import operator

from langgraph.graph import StateGraph, END

import main
import tools


class State(TypedDict):
    """图上流转的状态（就是一个字典，每个节点都能读、能改）。"""
    messages: Annotated[list, operator.add]   # 追加：节点返回的新消息接到历史后面
    memory: object                            # 这个用户专属的管家（参数传进来，不是全局）
    msg: object                               # 第一轮模型的原始返回
    reply: str                                # 最终要说给用户的话


# ============ 节点：每个节点 = 一个普通函数，收 state、吐"要更新的字段" ============

async def 节点_第一轮(state):
    """带工具问模型，让它自己决定喊不喊工具。"""
    try:
        response = await main.llm.achat(state["messages"], tools=tools.TOOLS)
    except Exception:
        main.logger.exception("第一轮 LLM 调用失败")
        return {"reply": main.FALLBACK_REPLY}     # 直接给兜底话术，judge 会送去收尾
    return {"msg": response.choices[0].message}


def 判断走哪(state):
    """条件边：返回下一站的名字。"""
    if state.get("reply"):                       # 第一轮已经失败，别再往下走
        return "收尾"
    if state["msg"].tool_calls:
        return "execute_tools"
    return "direct"


async def 节点_执行工具(state):
    """回填"模型喊了什么" + 逐个执行 + 回填"工具答了什么"。"""
    msg = state["msg"]
    新增消息 = [{
        "role": "assistant",
        "content": msg.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ],
    }]

    # 身份从管家拿（登录态），不从模型参数拿 —— 见 tools.execute 的说明
    当前用户 = getattr(state["memory"], "user_id", None)

    for tc in msg.tool_calls:
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments)         # JSON 字符串 → 字典
            result = await asyncio.to_thread(tools.execute, name, args, 当前用户)
        except Exception:
            main.logger.exception("工具 %s 执行失败", name)
            result = "系统内部错误，请转人工处理"
        新增消息.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })

    return {"messages": 新增消息}


async def 节点_第二轮(state):
    """不带工具再问一次，让模型把工具结果组织成客服话术。"""
    try:
        final = await main.llm.achat(state["messages"])       # 注意：没传 tools
    except Exception:
        main.logger.exception("第二轮 LLM 调用失败")
        return {"reply": main.FALLBACK_REPLY}
    return {"reply": final.choices[0].message.content}


def 节点_直接回复(state):
    """没喊工具（打招呼、闲聊）：第一轮的话就是最终回复。"""
    return {"reply": state["msg"].content or main.FALLBACK_REPLY}


def 节点_收尾(state):
    """把最终回复写回历史。理发和落盘在整张图跑完后统一做（见 answer_async）。"""
    return {"messages": [{"role": "assistant", "content": state["reply"]}]}


# ============ 画图 ============
builder = StateGraph(State)
builder.add_node("ask", 节点_第一轮)
builder.add_node("execute_tools", 节点_执行工具)
builder.add_node("answer", 节点_第二轮)
builder.add_node("direct", 节点_直接回复)
builder.add_node("收尾", 节点_收尾)

builder.set_entry_point("ask")
builder.add_conditional_edges(
    "ask",
    判断走哪,
    {"execute_tools": "execute_tools", "direct": "direct", "收尾": "收尾"},
)
builder.add_edge("execute_tools", "answer")
builder.add_edge("answer", "收尾")
builder.add_edge("direct", "收尾")
builder.add_edge("收尾", END)

app = builder.compile()


# ============ 对外接口：和 main.answer / main.answer_async 一模一样 ============

@main.计时器异步
async def answer_async(memory, q):
    """管家从参数进来 —— 这就是并发不串号的关键。"""
    messages = memory.messages
    main.确保人设(messages)
    messages.append({"role": "user", "content": q})

    结果 = await app.ainvoke({
        "messages": list(messages),      # 传副本进图，图的 reducer 会生成新列表
        "memory": memory,
    })

    # 图里流转完的完整历史（含本轮问答）搬回管家，再理发、落盘
    memory.messages[:] = 结果["messages"]
    await main.理发_async(memory.messages)
    await asyncio.to_thread(memory.persist)
    return 结果["reply"]


def answer(memory, q):
    """同步入口（终端 / Streamlit 用）：把异步图包一层。"""
    return asyncio.run(answer_async(memory, q))


if __name__ == "__main__":
    import Memory

    管家 = Memory.Memory(path="memory_graph_test.json")
    管家.load()
    print("图版客服：输入 exit 退出")
    while True:
        try:
            问题 = input("您：")
        except (KeyboardInterrupt, EOFError):
            break
        if not 问题.strip() or 问题.strip().lower() == "exit":
            break
        print("客服：", answer(管家, 问题))
