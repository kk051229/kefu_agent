import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class DeepSeekLLM:
    """DeepSeek 大模型的封装。

    DeepSeek 的接口与 OpenAI 完全兼容，所以直接用 openai 的 SDK,
    只需要把 base_url 换成 DeepSeek 的地址。
    """

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("没有找到 DEEPSEEK_API_KEY,请在 .env 文件中配置")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

    def chat(self, messages, tools=None):
        """发起一次对话。

        tools:function calling 的工具列表(JSON Schema)。
        不传 tools 就是普通对话；传了模型就可能返回 tool_calls。
        """
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        return self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            timeout=30,  # 30 秒没响应就报错，避免网络挂起时程序无限卡住
            **kwargs,
        )
