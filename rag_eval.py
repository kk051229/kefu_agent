"""RAG 评测脚本：每次改动检索逻辑后跑一遍，看效果是变好还是变坏。

用法：python rag_eval.py

指标：
- 命中@1：检索第一条就是标准答案
- 命中@3：前三条里有标准答案
- 覆盖@3：跨文档题要求的标准文档全部出现在前三条
- 阈值扫描：不同阈值下，域内通过率 vs 域外误放行率
"""
import knowledge

K = 3
阈值列表 = [0.85, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]

# 每题：问题、标准命中文档 id（跨文档题有多个）、类型
QUESTIONS = [
    # ---- 域内：直接问法 ----
    {"q": "退货政策是什么", "expect": ["p0"], "type": "直接"},
    {"q": "发货时间要多久", "expect": ["p1"], "type": "直接"},
    {"q": "运费怎么算", "expect": ["p2"], "type": "直接"},
    {"q": "怎么开发票", "expect": ["p3"], "type": "直接"},
    {"q": "客服工作时间是几点", "expect": ["p4"], "type": "直接"},
    {"q": "支持哪些支付方式", "expect": ["p11"], "type": "直接"},
    {"q": "优惠券可以叠加使用吗", "expect": ["p12"], "type": "直接"},

    # ---- 域内：换说法（口语化、错别字、代词）----
    {"q": "东西不想要了能退不", "expect": ["p0"], "type": "换说法"},
    {"q": "衣服破了能退吗", "expect": ["p6", "p0"], "type": "换说法"},
    {"q": "拍下多久能发货", "expect": ["p1"], "type": "换说法"},
    {"q": "满多少钱包邮", "expect": ["p2"], "type": "换说法"},
    {"q": "发票抬头写错了咋整", "expect": ["p14"], "type": "换说法"},
    {"q": "水果烂了怎么赔", "expect": ["p16"], "type": "换说法"},
    {"q": "尺码买大了能换吗", "expect": ["p17"], "type": "换说法"},
    {"q": "降价了能退差价吗", "expect": ["p19"], "type": "换说法"},
    {"q": "想取消订单怎么办", "expect": ["p8"], "type": "换说法"},
    {"q": "包裹显示签收但没收到", "expect": ["p10"], "type": "换说法"},
    {"q": "退款多久到账", "expect": ["p7"], "type": "换说法"},

    # ---- 域内：跨文档（答案需要两条知识）----
    {"q": "预售商品退款多久到账", "expect": ["p15", "p7"], "type": "跨文档"},
    {"q": "质量问题换货的运费谁承担", "expect": ["p6", "p17"], "type": "跨文档"},

    # ---- 域内：长文档切块（《大家电配送安装规范》，id 是 d0_序号）----
    {"q": "大家电包括哪些商品", "expect": ["d0_0"], "type": "长文档"},
    {"q": "没有电梯上楼费怎么收", "expect": ["d0_2"], "type": "长文档"},
    {"q": "安装空调的支架要另外付钱吗", "expect": ["d0_4"], "type": "长文档"},
    {"q": "大件退货没有原包装怎么办", "expect": ["d0_6"], "type": "长文档"},
    {"q": "大件家电保修多久", "expect": ["d0_7"], "type": "长文档"},
    {"q": "旧冰箱你们会上门拆走吗", "expect": ["d0_3"], "type": "长文档"},
    {"q": "电视送货上门要先验机再签收吗", "expect": ["d0_5"], "type": "长文档"},
    {"q": "大件商品配送超时怎么投诉", "expect": ["d0_1", "d0_9"], "type": "跨文档"},

    # ---- 域外：知识库没有，应该被阈值拦下 ----
    {"q": "今天天气怎么样", "expect": [], "type": "域外"},
    {"q": "你叫什么名字", "expect": [], "type": "域外"},
    {"q": "帮我写一首关于月亮的诗", "expect": [], "type": "域外"},
    {"q": "推荐一部好看的电影", "expect": [], "type": "域外"},
    {"q": "明天股票会涨吗", "expect": [], "type": "域外"},
    {"q": "帮我翻译一句英文", "expect": [], "type": "域外"},
]


def 跑评测():
    结果 = []
    for item in QUESTIONS:
        v = knowledge.embedder.embed(item["q"])
        r = knowledge.collection.query(query_embeddings=[v], n_results=K)
        结果.append({
            **item,
            "ids": r["ids"][0],
            "dists": r["distances"][0],
        })

    域内 = [x for x in 结果 if x["type"] != "域外"]
    域外 = [x for x in 结果 if x["type"] == "域外"]

    print("=" * 90)
    print("逐题结果")
    print("=" * 90)
    for x in 结果:
        if x["type"] == "域外":
            标记 = "（域外，应拦下）"
        elif x["ids"][0] in x["expect"]:
            标记 = "✅"
        else:
            标记 = f"❌ 期望 {','.join(x['expect'])}"
        top3 = "  ".join(
            f"{i}:{d:.3f}" for i, d in zip(x["ids"], x["dists"])
        )
        print(f"[{x['type']}] {x['q']}")
        print(f"    {top3}   {标记}")

    命中1 = sum(1 for x in 域内 if x["ids"][0] in x["expect"])
    命中3 = sum(1 for x in 域内 if any(i in x["expect"] for i in x["ids"]))
    跨文档 = [x for x in 域内 if len(x["expect"]) > 1]
    覆盖3 = sum(1 for x in 跨文档 if all(e in x["ids"] for e in x["expect"]))

    print("\n" + "=" * 90)
    print("汇总")
    print("=" * 90)
    print(f"域内题目: {len(域内)} 道")
    print(f"命中@1: {命中1}/{len(域内)}    命中@3: {命中3}/{len(域内)}")
    print(f"跨文档覆盖@3: {覆盖3}/{len(跨文档)}")

    域内距离 = [x["dists"][0] for x in 域内]
    域外距离 = [x["dists"][0] for x in 域外]
    print(f"域内 top1 距离: min {min(域内距离):.3f} / 平均 {sum(域内距离) / len(域内距离):.3f} / max {max(域内距离):.3f}")
    print(f"域外 top1 距离: min {min(域外距离):.3f} / 平均 {sum(域外距离) / len(域外距离):.3f} / max {max(域外距离):.3f}")

    print("\n" + "=" * 90)
    print("阈值扫描（top1 距离 < 阈值 才放行）")
    print("=" * 90)
    print(f"{'阈值':<8}{'域内通过率':<14}{'域外误放行率':<14}")
    for t in 阈值列表:
        域内通过 = sum(1 for x in 域内 if x["dists"][0] < t) / len(域内)
        域外误放 = sum(1 for x in 域外 if x["dists"][0] < t) / len(域外)
        print(f"{t:<10.2f}{域内通过:<16.0%}{域外误放:<14.0%}")


if __name__ == "__main__":
    跑评测()
