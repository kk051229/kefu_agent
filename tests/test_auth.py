"""登录与令牌的单测：密码哈希、签名、过期、篡改。

全是纯函数，不连数据库、不联网——注册/登录里用到的 db 函数换成假的。
"""
import pytest

import auth


# ============ 密码哈希 ============

def test_密码哈希_不是明文():
    哈希 = auth.生成密码哈希("123456")
    assert "123456" not in 哈希
    assert 哈希.startswith("pbkdf2_sha256$")


def test_密码对能验过_错验不过():
    哈希 = auth.生成密码哈希("123456")
    assert auth.验证密码("123456", 哈希)
    assert not auth.验证密码("1234567", 哈希)
    assert not auth.验证密码("", 哈希)


def test_同一个密码两次哈希不一样():
    """盐是随机的：就算数据库泄露，也不能靠"哈希相同"看出两个人用了同一个密码。"""
    assert auth.生成密码哈希("123456") != auth.生成密码哈希("123456")


def test_坏哈希当作验证失败不炸():
    assert auth.验证密码("x", "这不是哈希") is False
    assert auth.验证密码("x", None) is False


# ============ 令牌（JWT 手搓版） ============

def test_令牌签发验证往返():
    令牌 = auth.签发令牌("u001")
    assert 令牌.count(".") == 2          # header.payload.signature 三段
    assert auth.验证令牌(令牌) == "u001"


def test_令牌载荷被改_签名对不上():
    """把 u001 改成 u999：签名是按原文算的，改一个字就废了。"""
    令牌 = auth.签发令牌("u001")
    头, _, 签名 = 令牌.split(".")
    伪造载荷 = auth._b64(b'{"sub":"u999","iat":0,"exp":9999999999}')
    with pytest.raises(auth.令牌无效):
        auth.验证令牌(f"{头}.{伪造载荷}.{签名}")


def test_令牌过期():
    令牌 = auth.签发令牌("u001", 有效秒数=-1)   # 签发的那一刻就已经过期
    with pytest.raises(auth.令牌无效) as e:
        auth.验证令牌(令牌)
    assert "过期" in str(e.value)


def test_令牌乱写():
    for 乱写 in ["", "abc", "a.b", "a.b.c.d"]:
        with pytest.raises(auth.令牌无效):
            auth.验证令牌(乱写)


# ============ 注册 / 登录（数据库打假） ============

@pytest.fixture
def 假用户表(monkeypatch):
    """用内存字典冒充 users 表。monkeypatch 会在测试结束后自动还原。"""
    表 = {}
    monkeypatch.setattr(auth.db, "get_user", lambda uid: 表.get(uid))
    monkeypatch.setattr(
        auth.db, "create_user",
        lambda uid, h: 表.__setitem__(uid, {"user_id": uid, "password_hash": h}),
    )
    return 表


def test_注册后能登录(假用户表):
    auth.注册("u9", "pw123")
    assert auth.验证令牌(auth.登录("u9", "pw123")) == "u9"


def test_密码错登录失败(假用户表):
    auth.注册("u9", "pw123")
    with pytest.raises(auth.登录失败):
        auth.登录("u9", "pw456")


def test_账号不存在和密码错_报同一句话(假用户表):
    """不透露"账号是否注册过"：不然可以拿报错一个个试，摸出哪些账号存在。"""
    auth.注册("u9", "pw123")

    with pytest.raises(auth.登录失败) as 错密码:
        auth.登录("u9", "错的")
    with pytest.raises(auth.登录失败) as 无账号:
        auth.登录("根本没注册", "错的")

    assert str(错密码.value) == str(无账号.value)


def test_重复注册报错(假用户表):
    auth.注册("u9", "pw123")
    with pytest.raises(auth.登录失败):
        auth.注册("u9", "别的密码")
