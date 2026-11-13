"""图版大脑的路径测试：四条路一条一条走一遍。

关键手法：把 main.llm.achat 换成"假模型"，想让它说什么就说什么。
这样不用联网、不花钱、结果 100% 可复现——测 LLM 应用的标准姿势。
"""
import asyncio
import json
from types import SimpleNamespace

import graph
import main
import Memory


# ============ 造假工具：拼出和 OpenAI 返回一模一样的结构 ============

def 假回复(内容=None, 工具调用们=None):
    message = SimpleNamespace(content=内容, tool_calls=工具调用们 or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def 假工具调用(名字="check_order", 参数='{"order_id": "kx666"}'):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=名字, arguments=参数),
    )


def 建管家(tmp_path):
    管家 = Memory.Memory(path=str(tmp_path / "memory_test.json"), user_id="u001")
    管家.messages = []
    return 管家


def 角色们(管家):
    return [m["role"] for m in 管家.messages]


# ============ 四条路径 ============

def test_直接路_打招呼不调工具(tmp_path, monkeypatch):
    async def 假achat(messages, tools=None):
        return 假回复("您好呀～")

    monkeypatch.setattr(main.llm, "achat", 假achat)
    管家 = 建管家(tmp_path)

    回复 = asyncio.run(graph.answer_async(管家, "你好"))

    assert 回复 == "您好呀～"
    assert 角色们(管家) == ["system", "user", "assistant"]


def test_工具路_先调工具再组织话术(tmp_path, monkeypatch):
    第几次 = {"n": 0}

    async def 假achat(messages, tools=None):
        第几次["n"] += 1
        if 第几次["n"] == 1:
            return 假回复(None, [假工具调用()])
        return 假回复("订单 kx666 正在配送中～")

    执行记录 = []
    monkeypatch.setattr(main.llm, "achat", 假achat)
    monkeypatch.setattr(
        graph.tools, "execute",
        # 第三个参数是登录用户：图必须把管家身上的 user_id 传下去
        lambda name, args, 当前用户=None: 执行记录.append((name, args, 当前用户)) or "订单 kx666，配送中",
    )
    管家 = 建管家(tmp_path)

    回复 = asyncio.run(graph.answer_async(管家, "帮我查订单 kx666"))

    assert 回复 == "订单 kx666 正在配送中～"
    # 工具真的被调了，参数是从 JSON 字符串解析出来的，身份是管家的主人
    assert 执行记录 == [("check_order", {"order_id": "kx666"}, "u001")]
    # 历史里要留下"模型喊了什么、工具答了什么"两条名牌
    assert 角色们(管家) == ["system", "user", "assistant", "tool", "assistant"]


def test_第一轮就报错_给兜底话术(tmp_path, monkeypatch):
    async def 假achat(messages, tools=None):
        raise RuntimeError("网络炸了")

    monkeypatch.setattr(main.llm, "achat", 假achat)
    管家 = 建管家(tmp_path)

    回复 = asyncio.run(graph.answer_async(管家, "你好"))

    assert 回复 == main.FALLBACK_REPLY
    assert 角色们(管家) == ["system", "user", "assistant"]


def test_第二轮报错_也给兜底话术(tmp_path, monkeypatch):
    第几次 = {"n": 0}

    async def 假achat(messages, tools=None):
        第几次["n"] += 1
        if 第几次["n"] == 1:
            return 假回复(None, [假工具调用()])
        raise RuntimeError("第二轮炸了")

    monkeypatch.setattr(main.llm, "achat", 假achat)
    monkeypatch.setattr(graph.tools, "execute", lambda name, args, 当前用户=None: "订单信息")
    管家 = 建管家(tmp_path)

    回复 = asyncio.run(graph.answer_async(管家, "帮我查订单 kx666"))

    assert 回复 == main.FALLBACK_REPLY
    assert 角色们(管家) == ["system", "user", "assistant", "tool", "assistant"]


# ============ 记忆 ============

def test_多轮对话会累积到同一个管家(tmp_path, monkeypatch):
    async def 假achat(messages, tools=None):
        return 假回复("好的")

    monkeypatch.setattr(main.llm, "achat", 假achat)
    管家 = 建管家(tmp_path)

    asyncio.run(graph.answer_async(管家, "第一句"))
    asyncio.run(graph.answer_async(管家, "第二句"))

    assert 角色们(管家) == ["system", "user", "assistant", "user", "assistant"]
    assert 管家.messages[1]["content"] == "第一句"
    assert 管家.messages[3]["content"] == "第二句"


def test_对话会写进记忆文件(tmp_path, monkeypatch):
    async def 假achat(messages, tools=None):
        return 假回复("好的")

    monkeypatch.setattr(main.llm, "achat", 假achat)
    管家 = 建管家(tmp_path)

    asyncio.run(graph.answer_async(管家, "你好"))

    存下来的 = json.loads((tmp_path / "memory_test.json").read_text(encoding="utf-8"))
    assert 存下来的[-1] == {"role": "assistant", "content": "好的"}
