import json

数据 = [{"role": "user", "content": "帮我查订单 kx666"}]

# 保存：Python 对象 → JSON 文本 → 硬盘
with open("记忆.json", "w", encoding="utf-8") as f:
    json.dump(数据, f, ensure_ascii=False, indent=2)

# 加载：硬盘 → JSON 文本 → 活的 Python 对象（和原来一模一样）
with open("记忆.json", "r") as f:
    读回来的 = json.load(f)

读回来的.append({"role": "assistant", "content": "好的~"})   # 能继续用！
print(读回来的)