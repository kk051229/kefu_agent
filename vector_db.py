import chromadb
import knowledge

client=chromadb.PersistentClient(path="chroma_data")
collection = client.get_or_create_collection(
    name="policies",
    metadata={"hnsw:space":"cosine"},
    )

ids = []
documents = []
embeddings = []


for i,item in enumerate(knowledge.KNOWLEDGE):
    ids.append(f"p{i}")
    documents.append(item["content"])
    embeddings.append(item["vector"])

collection.add(
    ids=ids,
    documents=documents,
    embeddings=embeddings,
)

print("抽屉里现在有", collection.count(), "条知识")   # 验货：应该是 5


q_vec = knowledge.embedder.embed("你们家的退货政策是什么")
result = collection.query(
    query_embeddings=[q_vec],   # 问题向量——注意外面套个列表（可以一次问多个问题）
    n_results=1,                # 要最像的几条？先要 1 条
)
print(result)


questions = [
    "你们的退货政策是什么",
    "我买的衣服破了能退吗",
    "发货要多久",
    "运费怎么收的",
    "你们支持开发票吗",
    "今天天气怎么样",          # ← 无关问题，对照组
    "你叫什么名字",            # ← 无关问题，对照组
]
for q in questions:
    v = knowledge.embedder.embed(q)
    r = knowledge.collection.query(query_embeddings=[v], n_results=1)
    print(f"{q} → 距离 {r['distances'][0][0]:.3f} → 命中 {r['ids'][0][0]}")
