import os
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np

load_dotenv()

class EmbeddingModel:
    def __init__(self):
        api_key = os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("没有找到 SILICONFLOW_API_KEY,请在 .env 文件中配置")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.siliconflow.cn/v1",
        )                        # ← 到此为止，__init__ 收工

    def embed(self, text):       # ← 翻译官是独立方法，text 从参数来
        response = self.client.embeddings.create(
            model="BAAI/bge-m3",
            input=text,
        )
        return response.data[0].embedding

def cosine(a,b):
    """
    量两个向量的夹角,返回-1到1,越接近1越像

    """
    return np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b))

   
if __name__ == "__main__":
    model = EmbeddingModel()
    v = model.embed("退货政策")
    print("向量长度:", len(v))
    print("前 5 个数字:", v[:5])
