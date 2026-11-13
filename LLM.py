import logging

from llm_base import 模型客户端

logger = logging.getLogger(__name__)

# 进程启动以来的累计 token 用量：成本控制的第一步，是先"看得见"
累计用量 = {"输入": 0, "输出": 0}


def _记用量(response):
    """DeepSeek 每次都会在响应里带回 usage，以前直接扔了，现在记下来。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    累计用量["输入"] += getattr(usage, "prompt_tokens", 0) or 0
    累计用量["输出"] += getattr(usage, "completion_tokens", 0) or 0
    logger.info("token：本轮输入 %s，输出 %s | 累计 %s",
                usage.prompt_tokens, usage.completion_tokens, 累计用量)


class DeepSeekLLM(模型客户端):
    """DeepSeek 大模型的封装。

    DeepSeek 的接口与 OpenAI 完全兼容，所以直接用 openai 的 SDK,
    只需要把 base_url 换成 DeepSeek 的地址。
    """

    def __init__(self):
        super().__init__(
            "DEEPSEEK_API_KEY",
            "https://api.deepseek.com",
            "没有找到 DEEPSEEK_API_KEY,请在 .env 文件中配置",
        )

    def chat(self, messages, tools=None):
        """发起一次对话。

        tools:function calling 的工具列表(JSON Schema)。
        不传 tools 就是普通对话；传了模型就可能返回 tool_calls。
        """
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            timeout=30,  # 30 秒没响应就报错，避免网络挂起时程序无限卡住
            temperature=0.3,  # 客服场景：低温度，话术稳定、少发挥
            **kwargs,
        )
        _记用量(response)
        return response

    async def achat(self, messages, tools=None):
        """异步版 chat:等网络的时候把控制权交出去,不阻塞事件循环。"""
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        response = await self.取异步客户端().chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            timeout=30,
            temperature=0.3,
            **kwargs,
        )
        _记用量(response)
        return response

    async def astream(self, messages):
        """流式版:返回一个异步生成器,模型生成一小片就交出一小片。"""
        return await self.取异步客户端().chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True,
            timeout=30,
            temperature=0.3,
        )
