import numpy as np

from llm_base import 模型客户端


class EmbeddingModel(模型客户端):
    """硅基流动的 embedding 模型封装(bge-m3)。"""

    def __init__(self):
        super().__init__(
            "SILICONFLOW_API_KEY",
            "https://api.siliconflow.cn/v1",
            "没有找到 SILICONFLOW_API_KEY,请在 .env 文件中配置",
        )

    def embed(self, text):
        """把一段文字翻译成向量(1024 个数字)。"""
        response = self.client.embeddings.create(
            model="BAAI/bge-m3",
            input=text,
        )
        return response.data[0].embedding


def cosine(a, b):
    """量两个向量的夹角：返回 -1 到 1,越接近 1 越像。"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


if __name__ == "__main__":
    model = EmbeddingModel()
    v = model.embed("退货政策")
    print("向量长度:", len(v))
    print("前 5 个数字:", v[:5])
