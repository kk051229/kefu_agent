import embedding
import chromadb

embedder=embedding.EmbeddingModel()

# 知识库：公司的政策文档（RAG v0 版）
# 每条知识 = 一段内容 + 一组关键词（检索时靠关键词匹配）
KNOWLEDGE = [
    {
        "content": "退货政策：本店支持 7 天无理由退货。商品需保持完好、不影响二次销售。买家自行承担退货运费；如因商品质量问题退货，运费由本店承担。申请退货请提供订单号，退款将在收到退货后 3 个工作日内原路退回。",
        "keywords": ["退货", "退款", "七天", "无理由", "质量问题"],
    },
    {
        "content": "发货时间：现货商品付款后 48 小时内发货，预售商品以页面标注时间为准。法定节假日发货顺延。发货后可在订单详情中查看物流单号。",
        "keywords": ["发货", "多久", "什么时候发", "物流", "单号"],
    },
    {
        "content": "运费标准：全场满 99 元包邮，不满 99 元收取 8 元运费。偏远地区（新疆、西藏、青海等）运费 15 元，不参与包邮。",
        "keywords": ["运费", "包邮", "邮费", "快递费", "偏远"],
    },
    {
        "content": "发票：本店支持开具电子发票，下单时在订单备注中填写发票抬头即可。发票将在确认收货后 7 个工作日内发送到您的邮箱。",
        "keywords": ["发票", "开票", "报销", "抬头"],
    },
    {
        "content": "客服工作时间：在线客服服务时间为每天 9:00~21:00。非工作时间请留言，客服会在次日第一时间回复。",
        "keywords": ["客服", "工作时间", "几点", "人工"],
    },
]

for item in KNOWLEDGE:
    item["vector"]=embedder.embed(item["content"])




client = chromadb.PersistentClient(path="chroma_data")
collection = client.get_or_create_collection(
    name="policies",
    metadata={"hnsw:space": "cosine"},
)

collection.upsert(
    ids=[f"p{i}" for i in range(len(KNOWLEDGE))],
    documents=[item["content"] for item in KNOWLEDGE],
    embeddings=[item["vector"] for item in KNOWLEDGE],
)
