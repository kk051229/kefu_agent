import json
import os
class Memory:
    def __init__(self,path="memory.json"):
        self.path=path
        self.messages=[]

    def persist(self):
        with open(self.path,"w",encoding="utf-8")as f:
            json.dump(self.messages,f,ensure_ascii=False,indent=4)

    def load(self):
        if  os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.messages = json.load(f)
        else:
            self.messages=[]
