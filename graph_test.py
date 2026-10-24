import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from LLM import DeepSeekLLM
import tools

llm = DeepSeekLLM()

# ============================================================
# LangGraph 版客服：把你 main.py 的 answer() 翻译成一张图
#
# 核心概念：
#   1. state = 一个字典，在整张图里流转
#   2. 节点 = 普通函数：从 state 拿东西 → 干活 → return 一个「更新字典」
#      （重要坑：节点返回的字段是「覆盖」state 里的同名键）
#   3. 想要「追加」而不是「覆盖」，给字段装 reducer（减速器）：
#      Annotated[list, operator.add] = 新列表接到旧列表后面
# ============================================================


class State(TypedDict):
    """图纸上流转的状态：三个字段，各配各的处理方式。"""
    messages: Annotated[list, operator.add]  # 追加：节点返回的消息接到历史后面
    msg: object                              # 普通字段：覆盖（模型第一轮的话）
    reply: str                               # 普通字段：覆盖（最终回复）


def 节点_第一轮(state):
    """第一轮：带工具问模型，让模型决定要不要喊工具。"""
    response = llm.chat(state["messages"], tools=tools.TOOLS)
    msg = response.choices[0].message
    return {"msg": msg}                      # 只更新 msg，messages 原地不动


def 判断走哪(state):
    """裁判：模型喊了工具吗？返回下一站的名字。"""
    if state["msg"].tool_calls:
        return "execute_tools"
    return "direct"


def 节点_执行工具(state):
    """回填工具调用 + 逐个执行 + 回填结果，返回「新增消息列表」。"""
    msg = state["msg"]
    新增消息 = []

    # 回填 1：模型喊了什么（assistant 消息 + tool_calls）
    新增消息.append({
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
    })

    # 回填 2：逐个执行工具，结果以 role=tool 回填（tool_call_id 配对）
    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments)   # JSON 字符串 → 字典
            result = tools.execute(tc.function.name, args)
        except Exception:
            result = "系统内部错误，请转人工处理"
        新增消息.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })

    # reducer（operator.add）会把这份新列表接到历史后面
    return {"messages": 新增消息}


def 节点_第二轮(state):
    """第二轮：不带工具，让模型根据工具结果组织最终话术。"""
    response = llm.chat(state["messages"])           # 注意：没传 tools！
    reply = response.choices[0].message.content
    return {"reply": reply}


def 节点_直接回复(state):
    """没喊工具（比如打招呼）：第一轮的话就是最终回复。"""
    return {"reply": state["msg"].content}


# ============ 画图 ============
graph = StateGraph(State)                    # 图纸 + 状态结构
graph.add_node("ask", 节点_第一轮)
graph.add_node("execute_tools", 节点_执行工具)
graph.add_node("answer", 节点_第二轮)
graph.add_node("direct", 节点_直接回复)
graph.set_entry_point("ask")

graph.add_conditional_edges(
    "ask",
    判断走哪,
    {"execute_tools": "execute_tools", "direct": "direct"},
)
graph.add_edge("execute_tools", "answer")
graph.add_edge("answer", END)
graph.add_edge("direct", END)

app = graph.compile()


# ============ 测试 ============
if __name__ == "__main__":
    # 测试 1：查订单（走工具分支：ask → execute_tools → answer）
    result = app.invoke({
        "messages": [{"role": "user", "content": "帮我查一下订单 kx666"}],
    })
    print("查订单回复：", result["reply"])
    print()

    # 测试 2：打招呼（走直接回复：ask → direct）
    result2 = app.invoke({
        "messages": [{"role": "user", "content": "你好"}],
    })
    print("打招呼回复：", result2["reply"])
