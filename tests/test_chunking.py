"""切块器的单测：纯逻辑，不碰网络、不碰向量库。"""
import chunking


def test_短文本不切():
    assert chunking.切块("你好。", 块大小=100, 重叠=10) == ["你好。"]


def test_长文本切成多块():
    正文 = "。".join(f"这是第{i}句话" for i in range(200)) + "。"
    块们 = chunking.切块(正文, 块大小=100, 重叠=20)

    assert len(块们) > 1
    for 块 in 块们:
        assert 0 < len(块) <= 100 + 20 + 30   # 块大小 + 重叠 + 标题绑定留的余量


def test_空行被跳过():
    块们 = chunking.切块("\n\n第一段。\n\n\n第二段。\n", 块大小=100, 重叠=10)
    assert 块们 == ["第一段。第二段。"]


def test_标题和正文绑在同一块():
    正文 = "第一章 总则\n" + "正文内容。" * 30
    块们 = chunking.切块(正文, 块大小=50, 重叠=10)

    assert "第一章 总则" in 块们[0]
    # 标题后面就得跟着正文，不能一块只剩标题
    assert len(块们[0]) > len("第一章 总则")


def test_超长单句被硬切():
    正文 = "啊" * 500
    块们 = chunking.切块(正文, 块大小=100, 重叠=10)

    assert len(块们) >= 5
    assert all(len(块) <= 110 for 块 in 块们)


def test_加载文档_编号和出处(tmp_path):
    目录 = tmp_path / "docs"
    目录.mkdir()
    (目录 / "a.txt").write_text("第一段。\n第二段。", encoding="utf-8")
    (目录 / "b.txt").write_text("另一个文档。", encoding="utf-8")

    结果 = chunking.加载文档(str(目录))

    # 文件名按字典序排，所以 a.txt 是 d0，b.txt 是 d1
    assert 结果[0]["id"] == "d0_0"
    assert 结果[0]["content"].startswith("【a】")
    assert 结果[-1]["id"] == "d1_0"
    assert 结果[-1]["content"].startswith("【b】")


def test_加载文档_非txt被忽略(tmp_path):
    目录 = tmp_path / "docs"
    目录.mkdir()
    (目录 / "笔记.md").write_text("不是 txt。", encoding="utf-8")
    (目录 / "真文档.txt").write_text("是 txt。", encoding="utf-8")

    结果 = chunking.加载文档(str(目录))

    assert len(结果) == 1
    assert 结果[0]["id"] == "d0_0"          # 编号不被 .md 占位


def test_目录不存在返回空():
    assert chunking.加载文档("根本不存在的目录") == []
