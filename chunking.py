"""切块：把长文档切成约 300 字的小段，每段单独入库、单独检索。

为什么要切：整篇文档算一个向量，会被"平均"成一锅粥——问退货，
它可能因为文中出现过"发货"就被拉出来，但真正的退货段落埋在几千字里，
模型根本抓不住重点。切成小块后，命中的是段落，不是整篇。
"""
import os


def 切块(正文, 块大小=300, 重叠=60):
    """按段落切：短段落合并成块，长段落先按句拆，相邻块留一段重叠。

    重叠的作用：防止答案正好被切在边界上，两边都只拿到半句。
    """
    单元们 = []
    for 段 in 正文.split("\n"):
        段 = 段.strip()
        if not 段:
            continue
        if len(段) <= 块大小:
            单元们.append(段)
        else:
            单元们.extend(拆句(段, 块大小))

    # 章节标题（很短、没有句号）必须和后面的正文绑在一起，
    # 否则会出现"一块以'第三章 上楼与搬运费'结尾、正文在下一块"的尴尬
    绑定后 = []
    i = 0
    while i < len(单元们):
        单元 = 单元们[i]
        if (len(单元) < 30 and "。" not in 单元 and "！" not in 单元
                and "？" not in 单元 and i + 1 < len(单元们)):
            绑定后.append(单元 + "\n" + 单元们[i + 1])
            i += 2
        else:
            绑定后.append(单元)
            i += 1
    单元们 = 绑定后

    块们 = []
    当前 = ""
    for 单元 in 单元们:
        if 当前 and len(当前) + len(单元) > 块大小:
            块们.append(当前)
            当前 = 留尾巴(当前, 重叠)              # 尾巴留一截，接到下一块开头
        当前 += 单元
    if 当前.strip():
        块们.append(当前)
    return 块们


def 留尾巴(当前, 重叠):
    """取最后 重叠 个字做重叠部分，并且从句子开头开始，别让新块从半句话起头。"""
    if not 重叠:
        return ""
    尾巴 = 当前[-重叠:]
    位置 = 尾巴.find("。")
    if 位置 != -1:
        尾巴 = 尾巴[位置 + 1:]
    return 尾巴


def 拆句(段, 块大小):
    """长段落 → 一句一句，再把句子装成不超过块大小的包。"""
    句们 = []
    当前 = ""
    for 字 in 段:
        当前 += 字
        if 字 in "。！？":
            句们.append(当前)
            当前 = ""
    if 当前:
        句们.append(当前)

    结果 = []
    当前 = ""
    for 句 in 句们:
        if len(句) > 块大小:                 # 一句就超长 → 只能硬切
            if 当前:
                结果.append(当前)
                当前 = ""
            结果.extend(句[i:i + 块大小] for i in range(0, len(句), 块大小))
        elif len(当前) + len(句) > 块大小:
            结果.append(当前)
            当前 = 句
        else:
            当前 += 句
    if 当前:
        结果.append(当前)
    return 结果


def 加载文档(目录="docs"):
    """读目录下所有 .txt，切成块；每块带上文档名，检索出来才知道出处。"""
    结果 = []
    if not os.path.isdir(目录):
        return 结果
    序号 = 0
    for 文件名 in sorted(os.listdir(目录)):
        if not 文件名.endswith(".txt"):
            continue
        文档名 = os.path.splitext(文件名)[0]
        with open(os.path.join(目录, 文件名), "r", encoding="utf-8") as f:
            正文 = f.read()
        for i, 块 in enumerate(切块(正文)):
            结果.append({
                # 注意：增删文档会让编号整体前移，评测集里写死的 d0_2 也要跟着改。
                # 学习阶段够用；生产里一般用"文档 id + 块号"，不靠排序位置。
                "id": f"d{序号}_{i}",
                "content": f"【{文档名}】{块}",   # 带上出处，块才不会"没头没脑"
                "source": 文档名,
            })
        序号 += 1
    return 结果
