import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class 模型客户端:
    """所有大模型客户端的父类：负责查钥匙、造 OpenAI 传话员。

    子类只需要 super().__init__(...) 填三个参数：
    key名(.env 里的钥匙名)、门牌号(base_url)、报错文案。
    """

    def __init__(self, key名, 门牌号, 报错文案):
        api_key = os.getenv(key名)
        if not api_key:
            raise RuntimeError(报错文案)
        self.client = OpenAI(
            api_key=api_key,
            base_url=门牌号,
        )
