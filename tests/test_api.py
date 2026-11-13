"""HTTP 层测试：只测"接口这层"对不对，大脑用假的。

TestClient 是 FastAPI 自带的测试客户端：不用真的起 uvicorn，
请求直接打进 app，速度飞快。

登录之后，凡是"要身份"的接口都得先换一张令牌：
POST /login 用假用户表换 token → 之后每个请求带 Authorization 头。
"""
import pytest
from fastapi.testclient import TestClient

import api
import auth
import Memory
import 限流

client = TestClient(api.app)

# 模块加载时算一次密码哈希（pbkdf2 有点慢，别在每个测试里重算）
哈希 = auth.生成密码哈希("123456")


@pytest.fixture(autouse=True)
def 每个测试前清空限流():
    """限流计数器是模块级全局的，不清空会串到下一个测试里。"""
    限流.清空()
    yield
    限流.清空()


def _装上假用户表(monkeypatch, 用户们=("u001", "u002")):
    """冒充 users 表：这两个账号的密码都是 123456。"""
    monkeypatch.setattr(
        api.db, "get_user",
        lambda uid: {"user_id": uid, "password_hash": 哈希} if uid in 用户们 else None,
    )


def _拿令牌(monkeypatch, user_id="u001"):
    """走一遍真的 POST /login，拿一个能用于后续请求的请求头。"""
    _装上假用户表(monkeypatch)
    r = client.post("/login", json={"user_id": user_id, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _假管家(tmp_path):
    管家 = Memory.Memory(path=str(tmp_path / "memory_api_test.json"), user_id="u001")
    管家.messages = []
    return 管家


def _接上假大脑(tmp_path, monkeypatch, 回复="好的"):
    """把"找管家"和"图版大脑"都换掉，只测 HTTP 这层。"""
    记下 = {}

    def 假找管家(user_id):
        记下["user_id"] = user_id
        return _假管家(tmp_path)

    monkeypatch.setattr(api, "找管家", 假找管家)

    async def 假回答(管家, q):
        return 回复

    monkeypatch.setattr(api.graph, "answer_async", 假回答)
    return 记下


# ============ 基础接口 ============

def test_hello():
    r = client.get("/hello")
    assert r.status_code == 200
    assert r.json() == {"msg": "你好，世界"}


# ============ 注册 / 登录 ============

def test_登录成功拿到令牌(monkeypatch):
    _装上假用户表(monkeypatch)
    r = client.post("/login", json={"user_id": "u001", "password": "123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert auth.验证令牌(body["token"]) == "u001"     # 发出来的令牌验得通


def test_密码错返回401(monkeypatch):
    _装上假用户表(monkeypatch)
    r = client.post("/login", json={"user_id": "u001", "password": "错的"})
    assert r.status_code == 401


def test_账号不存在返回401(monkeypatch):
    _装上假用户表(monkeypatch)
    r = client.post("/login", json={"user_id": "nobody", "password": "123456"})
    assert r.status_code == 401


def test_注册成功_存的是哈希(monkeypatch):
    注册记录 = []
    monkeypatch.setattr(api.db, "get_user", lambda uid: None)          # 没人注册过
    monkeypatch.setattr(api.db, "create_user",
                        lambda uid, h: 注册记录.append((uid, h)))

    r = client.post("/register", json={"user_id": "u9", "password": "pw"})
    assert r.status_code == 200
    assert 注册记录[0][0] == "u9"
    assert 注册记录[0][1].startswith("pbkdf2_sha256$")                 # 存的是哈希不是明文


def test_重复注册返回409(monkeypatch):
    _装上假用户表(monkeypatch)
    r = client.post("/register", json={"user_id": "u001", "password": "pw"})
    assert r.status_code == 409


# ============ 没令牌寸步难行 ============

def test_没令牌访问chat返回401():
    r = client.post("/chat", json={"message": "你好"})
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("WWW-Authenticate", "")


def test_令牌乱写返回401():
    # 注意：HTTP 请求头只能放 ASCII，这里用英文乱码（放中文 httpx 会直接报编码错）
    r = client.post("/chat", json={"message": "你好"},
                    headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_没令牌查订单也返回401():
    assert client.get("/orders/kx666").status_code == 401


# ============ 订单接口的归属校验 ============

def test_订单不存在返回404(monkeypatch):
    token = _拿令牌(monkeypatch)
    monkeypatch.setattr(api.db, "get_order", lambda order_id: None)
    r = client.get("/orders/no_such_order", headers=token)
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


def test_自己的订单返回200(monkeypatch):
    token = _拿令牌(monkeypatch)
    monkeypatch.setattr(api.db, "get_order",
                        lambda order_id: {"order_id": order_id, "user_id": "u001", "status": "配送中"})
    r = client.get("/orders/kx666", headers=token)
    assert r.status_code == 200
    assert r.json()["status"] == "配送中"


def test_别人的订单也返回404(monkeypatch):
    """不能让人靠试订单号摸出"哪些单真实存在"。"""
    token = _拿令牌(monkeypatch)
    monkeypatch.setattr(api.db, "get_order",
                        lambda order_id: {"order_id": order_id, "user_id": "u002", "status": "配送中"})
    assert client.get("/orders/kx666", headers=token).status_code == 404


# ============ 健康检查（不能要求登录，负载均衡器手里没令牌） ============

def test_健康检查_数据库正常(monkeypatch):
    monkeypatch.setattr(api.db, "get_order", lambda order_id: None)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_健康检查_数据库挂了返回503(monkeypatch):
    def 炸了(order_id):
        raise RuntimeError("连不上 MySQL")

    monkeypatch.setattr(api.db, "get_order", 炸了)
    r = client.get("/health")
    assert r.status_code == 503


# ============ /chat 的校验 ============

def test_空消息被Pydantic拦下(monkeypatch):
    token = _拿令牌(monkeypatch)
    r = client.post("/chat", json={"message": ""}, headers=token)
    assert r.status_code == 422


def test_超长消息被拦下(monkeypatch):
    token = _拿令牌(monkeypatch)
    r = client.post("/chat", json={"message": "字" * 501}, headers=token)
    assert r.status_code == 422


def test_纯空格返回400(monkeypatch):
    token = _拿令牌(monkeypatch)
    r = client.post("/chat", json={"message": "   "}, headers=token)
    assert r.status_code == 400


# ============ /chat 正常路 ============

def test_聊天正常(tmp_path, monkeypatch):
    token = _拿令牌(monkeypatch)
    _接上假大脑(tmp_path, monkeypatch, 回复="您好呀～")
    r = client.post("/chat", json={"message": "你好"}, headers=token)
    assert r.status_code == 200
    assert r.json() == {"reply": "您好呀～"}


def test_请求体里塞user_id也没用(tmp_path, monkeypatch):
    """身份只认令牌：请求体里写 u999，实际还是令牌里的 u001。"""
    token = _拿令牌(monkeypatch)
    记下 = _接上假大脑(tmp_path, monkeypatch)
    r = client.post("/chat", json={"user_id": "u999", "message": "你好"}, headers=token)
    assert r.status_code == 200
    assert 记下["user_id"] == "u001"


# ============ 限流（key 现在是令牌里的用户） ============

def test_超过每分钟上限返回429(tmp_path, monkeypatch):
    token = _拿令牌(monkeypatch)
    _接上假大脑(tmp_path, monkeypatch)

    for _ in range(限流.每分钟上限):
        r = client.post("/chat", json={"message": "你好"}, headers=token)
        assert r.status_code == 200

    r = client.post("/chat", json={"message": "你好"}, headers=token)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_限流按用户分开算(tmp_path, monkeypatch):
    tokenA = _拿令牌(monkeypatch, "u001")
    tokenB = _拿令牌(monkeypatch, "u002")
    _接上假大脑(tmp_path, monkeypatch)

    for _ in range(限流.每分钟上限):
        client.post("/chat", json={"message": "你好"}, headers=tokenA)

    # A 被限流了，B 不受影响
    assert client.post("/chat", json={"message": "你好"}, headers=tokenA).status_code == 429
    assert client.post("/chat", json={"message": "你好"}, headers=tokenB).status_code == 200
