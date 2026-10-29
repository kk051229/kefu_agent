from llm_base import 模型客户端


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
        return self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            timeout=30,  # 30 秒没响应就报错，避免网络挂起时程序无限卡住
            **kwargs,
        )
