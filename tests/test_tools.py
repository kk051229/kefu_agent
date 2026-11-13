"""工具层单测：不连数据库、不调模型，全部用假的替换掉。

为什么要假：单测要测的是"我们的逻辑对不对"，不是"MySQL 通不通"。
数据库/网络一旦参与，测试就会慢、会飘、换台电脑就跑不了。

登录之后多了一条主线：**身份和归属**。
- 没登录 → 让用户先登录；
- 单子不是你的 → 和"没找到"回同一句话（不透露订单存不存在）。
"""
import tools


def _订单(order_id="kx666", 主人="u001", status="配送中", address="北京朝阳区"):
    return {"order_id": order_id, "user_id": 主人, "status": status, "address": address}


# ============ check_order ============

def test_查订单_存在且是自己的(monkeypatch):
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: _订单(order_id))
    结果 = tools.check_order("kx666", 当前用户="u001")
    assert "kx666" in 结果
    assert "配送中" in 结果
    assert "北京朝阳区" in 结果


def test_查订单_不存在(monkeypatch):
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: None)
    assert "没有找到" in tools.check_order("kx000", 当前用户="u001")


def test_查订单_是别人的单也报没找到(monkeypatch):
    """不能让人靠试订单号摸出"哪些单真实存在"，所以别人的单只说没找到。"""
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: _订单(order_id, 主人="u002"))
    assert "没有找到" in tools.check_order("kx666", 当前用户="u001")


def test_查订单_没登录先登录(monkeypatch):
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: _订单(order_id))
    assert "请先登录" in tools.check_order("kx666")


# ============ change_address ============

def test_改地址_成功(monkeypatch):
    monkeypatch.setattr(tools.db, "update_order", lambda order_id, addr, uid: 1)
    结果 = tools.change_address("kx666", "新地址", 当前用户="u001")
    assert "已经修改" in 结果


def test_改地址_不是你的单改不动(monkeypatch):
    """UPDATE 的 WHERE 里带了 user_id：不是你的单，影响行数就是 0。"""
    被调用 = []

    def 假更新(order_id, addr, uid):
        被调用.append((order_id, addr, uid))
        return 0                      # 一行都没改到

    monkeypatch.setattr(tools.db, "update_order", 假更新)
    assert "没有找到" in tools.change_address("kx666", "新地址", 当前用户="u001")
    assert 被调用 == [("kx666", "新地址", "u001")]   # 带上登录用户去改，改不到


# ============ update_order_status ============

def test_改状态_订单不存在就不改(monkeypatch):
    """铁律：先查后改。查不到就刹车，UPDATE 一次都不能发。"""
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: None)

    被调用 = []
    monkeypatch.setattr(tools.db, "update_order_status",
                        lambda order_id, status, uid: 被调用.append((order_id, status)))

    assert "没有找到" in tools.update_order_status("kx000", "已签收", 当前用户="u001")
    assert 被调用 == []


def test_改状态_是别人的单也不改(monkeypatch):
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: _订单(order_id, 主人="u002"))

    被调用 = []
    monkeypatch.setattr(tools.db, "update_order_status",
                        lambda order_id, status, uid: 被调用.append((order_id, status)))

    assert "没有找到" in tools.update_order_status("kx666", "已签收", 当前用户="u001")
    assert 被调用 == []


def test_改状态_订单存在且是自己的才改(monkeypatch):
    monkeypatch.setattr(tools.db, "get_order", lambda order_id: _订单(order_id))
    被调用 = []
    monkeypatch.setattr(tools.db, "update_order_status",
                        lambda order_id, status, uid: 被调用.append((order_id, status, uid)))

    assert "已经修改成已签收" in tools.update_order_status("kx666", "已签收", 当前用户="u001")
    assert 被调用 == [("kx666", "已签收", "u001")]


# ============ get_coupon（查谁的券由登录态决定） ============

def test_优惠券_查的是登录用户(monkeypatch):
    查过谁 = []
    monkeypatch.setattr(tools.db, "get_coupons",
                        lambda uid: 查过谁.append(uid) or [{"id": 1, "coupon_name": "满100-10", "amount": 10}])

    结果 = tools.get_coupon(当前用户="u001")
    assert "满100-10" in 结果
    assert 查过谁 == ["u001"]


def test_优惠券_没登录先登录():
    assert "请先登录" in tools.get_coupon()


# ============ search_policy（检索的放行逻辑） ============

def _假装检索(monkeypatch, 文档们, 距离们):
    """把"算向量 + 查 Chroma"整段替换成固定结果，只测放行逻辑。"""
    monkeypatch.setattr(tools.knowledge.embedder, "embed", lambda text: [0.0] * 1024)
    monkeypatch.setattr(
        tools.knowledge.collection, "query",
        lambda **kwargs: {
            "ids": [[f"p{i}" for i in range(len(文档们))]],
            "documents": [文档们],
            "distances": [距离们],
        },
    )


def test_检索_够像就放行(monkeypatch):
    _假装检索(monkeypatch, ["退货政策原文"], [0.60])
    assert tools.search_policy("怎么退货") == "退货政策原文"


def test_检索_不够像就拒答(monkeypatch):
    """第 1 名都超过 0.95，说明知识库里没有，后面几条一律不要。"""
    _假装检索(monkeypatch, ["八竿子打不着"], [1.10])
    assert "没有找到" in tools.search_policy("今天天气怎么样")


def test_检索_多条命中拼成资料(monkeypatch):
    _假装检索(monkeypatch, ["资料甲", "资料乙", "太远的丙"], [0.50, 0.70, 1.20])
    结果 = tools.search_policy("预售商品退款多久到账")
    assert "[资料1] 资料甲" in 结果
    assert "[资料2] 资料乙" in 结果
    assert "资料丙" not in 结果          # 超过阈值的第三条被过滤掉


# ============ execute 登记簿 ============

def test_未知工具():
    assert "未知工具" in tools.execute("不存在的工具", {})


def test_execute_身份只认登录态_模型给的user_id被丢掉(monkeypatch):
    """模型参数里混进来的 user_id 必须无效——身份不能自己宣布。"""
    收到 = {}

    def 假查订单(order_id, 当前用户=None):
        收到["order_id"] = order_id
        收到["当前用户"] = 当前用户
        return "ok"

    monkeypatch.setattr(tools, "check_order", 假查订单)

    结果 = tools.execute("check_order", {"order_id": "kx666", "user_id": "u999"}, 当前用户="u001")

    assert 结果 == "ok"
    assert 收到 == {"order_id": "kx666", "当前用户": "u001"}   # u999 被丢掉了
