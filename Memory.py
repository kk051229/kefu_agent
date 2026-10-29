import json
import os
class Memory:
    def __init__(self,path="memory.json"):
        self.path=path
        self.messages=[]

    def __str__(self):
        return f"管家({self.path},{len(self.messages)} 条消息)"

    def persist(self):
        with open(self.path,"w",encoding="utf-8")as f:
            json.dump(self.messages,f,ensure_ascii=False,indent=4)

    def load(self):
        if  os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.messages = json.load(f)
        else:
            self.messages=[]

# 测试代码放 __main__ 里：只有直接运行 python Memory.py 才执行
if __name__ == "__main__":
    管家 = Memory(path="memory_u001.json")
    print(管家)
