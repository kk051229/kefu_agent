import json
import logging
import Memory


import tools
from LLM import DeepSeekLLM

# 日志是给开发人员看的，用户看不到；logger.exception 会自动带上完整的报错堆栈
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SYSTEM = """你是一名工作经验丰富、态度良好的专业客服。
规则：
1. 当需要查询订单、办理退款、或遇到解决不了的问题时，调用对应的工具；
2. 如果用户只是打招呼或闲聊，不需要调用工具，直接友好地回答即可；
3. 拿到工具的执行结果后，用和善、亲切的口吻组织语言回复用户，不要输出 JSON。"""

llm = DeepSeekLLM()
memory=Memory.Memory()

# 给客户看的兜底话术：具体错误只进日志，不让客户看到
FALLBACK_REPLY = "抱歉，系统暂时开小差了，请稍后再试~"


def answer(messages,q):
    messages.append({
            "role": "user",
            "content": q,
    })

    # 第一轮：让模型决定"要不要用工具、用哪个工具"
    # 返回的 tool_calls 是 API 保证的结构化数据，参数不会再丢
    try:
        response = llm.chat(messages, tools=tools.TOOLS)
    except Exception:
        logger.exception("第一轮 LLM 调用失败")
        reply= FALLBACK_REPLY
    else:
        msg = response.choices[0].message

    # 模型觉得不需要工具（比如打招呼），直接用它的回答
        if not msg.tool_calls:
            reply= msg.content or FALLBACK_REPLY

        # 把模型的"工具调用"原样放回消息里，让模型记得自己叫过哪个工具
        else:
            messages.append({
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

        # 逐个执行工具，把结果以 role="tool" 的格式放回消息
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                    result = tools.execute(name, args)
                except Exception:
                    logger.exception("工具 %s 执行失败", name)
                    result = "系统内部错误，请转人工处理"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # 第二轮：不带工具，让模型根据工具结果生成最终话术
            try:
                final = llm.chat(messages)
            except Exception:
                logger.exception("第二轮 LLM 调用失败")
                reply= FALLBACK_REPLY
            else:
                reply= final.choices[0].message.content

    messages.append({
        "role": "assistant",
        "content": reply,
    })


  
    memory.persist()
    return reply

def main():
    global memory                                    # 声明：要改的是全局管家
    user_id = input("请输入您的用户编号：").strip()
    if not user_id:
        user_id = "guest"                            # 没输入就用默认编号
    memory = Memory.Memory(path=f"memory_{user_id}.json")   # 换管家：每人一个记忆文件
    memory.load()                                    # 新管家读盘
    print("客服：您好，请问有什么可以帮您？（输入 exit 退出）")
    while True:
        try:
            q = input("您：")
        except (KeyboardInterrupt, EOFError):
            print("\n客服:再见,祝您生活愉快~")
            break
        if not q.strip():
            continue
        if q.strip().lower() == "exit":
            print("客服：再见，祝您生活愉快~")
            break
        print("客服：", answer(memory.messages, q))


if __name__ == "__main__":
    main()
