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


async def 执行工具并回填(msg, 当前用户):
    """把模型喊的工具逐个执行，返回要追加的消息（图版和流式版共用这段）。

    返回两条牌子：
    - assistant：模型喊了什么（带 tool_calls，后面要原样存进历史）
    - tool：工具答了什么（带 tool_call_id，和上面的调用配对）
    """
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

    return 新增消息


async def 节点_执行工具(state):
    """图里的工具节点：身份从管家拿（登录态），不从模型参数拿。"""
    当前用户 = getattr(state["memory"], "user_id", None)
    return {"messages": await 执行工具并回填(state["msg"], 当前用户)}


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


# ============ 流式版：一边生成一边交卷 ============

async def answer_stream_async(memory, q):
    """流式版大脑：每生成一小片，就 yield 一小片。

    和 answer_async 的区别只在"怎么交卷"：
    - 普通版：整段生成完，一次性 return
    - 流式版：出来一片交一片，API 层边收边转发给用户

    为什么第一轮不能流：模型可能正在决定"要不要调工具"，
    这时候没有话可说。所以第一轮先正常问（不流），
    如果它喊了工具，执行完再流第二轮（组织话术）；
    如果它直接回答（打招呼），那就把整段一次给出去。
    """
    messages = memory.messages
    main.确保人设(messages)
    messages.append({"role": "user", "content": q})

    reply = main.FALLBACK_REPLY
    try:
        response = await main.llm.achat(messages, tools=tools.TOOLS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            # 直接回复：模型已经整段生成完了，没有流的意义，一次给
            reply = msg.content or main.FALLBACK_REPLY
            yield reply
        else:
            # 工具轮：先把"喊了什么/答了什么"回填进历史
            messages.extend(await 执行工具并回填(msg, memory.user_id))

            # 第二轮才是真流式：出来一片，交一片
            片们 = []
            async for chunk in main.llm.astream(messages):
                if not chunk.choices:              # 最后一片可能只带 usage，没有内容
                    continue
                小片 = chunk.choices[0].delta.content
                if 小片:
                    片们.append(小片)
                    yield 小片
            reply = "".join(片们) or main.FALLBACK_REPLY
    except Exception:
        main.logger.exception("流式回答失败")
        reply = main.FALLBACK_REPLY
        yield reply
    finally:
        # 不管用户看到多少，历史都要收尾：写回回复 → 理发 → 落盘
        messages.append({"role": "assistant", "content": reply})
        await main.理发_async(messages)
        await asyncio.to_thread(memory.persist)


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
