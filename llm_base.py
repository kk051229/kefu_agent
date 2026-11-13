import asyncio
import os

from openai import OpenAI, AsyncOpenAI
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
        # 异步客户端不能提前造死：它的连接池绑在"当前这个事件循环"上，
        # 换一个 loop（比如 asyncio.run 每次都新建）旧客户端就会报 Event loop is closed。
        # 所以按需发放，每个 loop 配一个。
        self._钥匙 = api_key
        self._门牌号 = 门牌号
        self._async_client = None
        self._async_loop = None
        self._旧客户端们 = []          # 留着引用：它们的 loop 已经关了，被回收时去关连接会报错

    def 取异步客户端(self):
        loop = asyncio.get_running_loop()
        if self._async_loop is not loop:
            if self._async_client is not None:
                self._旧客户端们.append(self._async_client)
            self._async_client = AsyncOpenAI(api_key=self._钥匙, base_url=self._门牌号)
            self._async_loop = loop
        return self._async_client
