"""登录与令牌：密码存哈希，登录发令牌。

两个核心问题：

1. 密码怎么存？——**绝不能存明文**。存的是"加盐哈希":
   同一个密码每次存出来都不一样（因为盐随机），但可以验证对不对。
   数据库泄露了，攻击者也拿不回原密码。

2. 登录之后怎么记住"你是谁"？——发一张**令牌(token)**。
   令牌是我们用密钥签过名的:内容看得见(base64 不是加密！），
   但改一个字签名就对不上。服务器不用记任何东西，
   拿到令牌验一下签名，就知道"这是不是我发的、有没有被人改过"。

JWT 手搓版(HS256):说白了就是"两段 base64 + 一段 HMAC 签名"。
生产项目请直接 pip install pyjwt:这里手搓是为了让你看清里面到底是什么。
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

import db

logger = logging.getLogger(__name__)

哈希迭代次数 = 200_000        # 迭代越多越难暴力破解、也越慢。20 万次约 0.1 秒，够用
令牌有效秒数 = 2 * 60 * 60     # 令牌 2 小时后过期，过期要重新登录

_兜底密钥 = None


# ============ 密码：存哈希，不存明文 ============

def 生成密码哈希(密码):
    """格式：算法$迭代次数$盐$摘要。盐也一起存，因为验证时要用它重算。"""
    盐 = secrets.token_hex(16)    # 每个用户一个随机盐：同样的密码，存出来也完全不同
    摘要 = hashlib.pbkdf2_hmac(
        "sha256", 密码.encode("utf-8"), bytes.fromhex(盐), 哈希迭代次数
    )
    return f"pbkdf2_sha256${哈希迭代次数}${盐}${摘要.hex()}"


def 验证密码(密码, 存的哈希):
    """拿用户输入的密码，用存着的盐重新算一遍，看结果对不对。"""
    try:
        算法, 次数, 盐, 摘要hex = 存的哈希.split("$")
        if 算法 != "pbkdf2_sha256":
            return False
        摘要 = hashlib.pbkdf2_hmac(
            "sha256", 密码.encode("utf-8"), bytes.fromhex(盐), int(次数)
        )
    except (ValueError, AttributeError, TypeError):
        return False              # 哈希格式坏了 → 当作验证失败，别让程序炸

    # 用"定长时间比较"：普通的 == 一旦发现不同就立刻返回，
    # 攻击者能靠响应耗时一位一位猜出摘要。compare_digest 无论对错都花同样的时间。
    return hmac.compare_digest(摘要.hex(), 摘要hex)


# ============ 令牌：JWT 手搓版 ============

def _密钥():
    """签名用的密钥。放在 .env 的 JWT_SECRET 里，绝不能在代码里写死。"""
    global _兜底密钥
    密钥 = os.getenv("JWT_SECRET", "")
    if 密钥:
        return 密钥.encode("utf-8")
    if _兜底密钥 is None:
        _兜底密钥 = secrets.token_hex(32)
        logger.warning("没有配置 JWT_SECRET，本进程临时用随机密钥——重启后所有令牌都会失效")
    return _兜底密钥.encode("utf-8")


def _b64(字节):
    """base64url 编码，去掉尾巴上的 =（JWT 的标准写法）。"""
    return base64.urlsafe_b64encode(字节).rstrip(b"=").decode("ascii")


def _解b64(文本):
    补 = "=" * (-len(文本) % 4)    # 长度不是 4 的倍数就补 =，解码器才认
    return base64.urlsafe_b64decode(文本 + 补)


def 签发令牌(user_id, 有效秒数=令牌有效秒数):
    """登录成功后发一张：header.payload.signature 三段，用 . 连起来。"""
    现在 = int(time.time())
    头 = {"alg": "HS256", "typ": "JWT"}
    载荷 = {"sub": user_id, "iat": 现在, "exp": 现在 + 有效秒数}

    前两段 = ".".join([
        _b64(json.dumps(头, separators=(",", ":")).encode("utf-8")),
        _b64(json.dumps(载荷, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
    ])
    签名 = hmac.new(_密钥(), 前两段.encode("ascii"), hashlib.sha256).digest()
    return f"{前两段}.{_b64(签名)}"


class 令牌无效(Exception):
    """令牌是假的、被改过、或者过期了。API 层见到它就返回 401。"""


def 验证令牌(令牌):
    """验签名 → 查过期 → 返回 user_id。任何一步不对都抛 令牌无效。"""
    try:
        头段, 载荷段, 签名段 = 令牌.split(".")
    except (AttributeError, ValueError):
        raise 令牌无效("令牌格式不对")

    前两段 = f"{头段}.{载荷段}"
    期望签名 = _b64(hmac.new(_密钥(), 前两段.encode("ascii"), hashlib.sha256).digest())

    # 先验签名再解内容：签名不对，里面写什么都不用看了
    if not hmac.compare_digest(期望签名, 签名段):
        raise 令牌无效("签名对不上，令牌可能是伪造的")

    try:
        载荷 = json.loads(_解b64(载荷段))
    except (ValueError, UnicodeDecodeError):
        raise 令牌无效("令牌内容解不开")

    if int(载荷.get("exp", 0)) < int(time.time()):
        raise 令牌无效("令牌已过期，请重新登录")

    user_id = 载荷.get("sub")
    if not user_id:
        raise 令牌无效("令牌里没有用户")
    return user_id


# ============ 注册 / 登录 ============

class 登录失败(Exception):
    """账号不存在、密码错、重复注册……给用户看的失败原因。"""


def 注册(user_id, 密码):
    if not user_id or not 密码:
        raise 登录失败("账号和密码都不能为空")
    if db.get_user(user_id) is not None:
        raise 登录失败("这个账号已经被注册了")
    db.create_user(user_id, 生成密码哈希(密码))


def 登录(user_id, 密码):
    """验证通过返回令牌；失败统一抛"账号或密码不对"。

    不区分"账号不存在"和"密码错"：不然别人可以拿报错信息
    一个个试，把"哪些账号存在"全摸出来。
    """
    row = db.get_user(user_id)
    if row is None or not 验证密码(密码, row["password_hash"]):
        raise 登录失败("账号或密码不对")
    return 签发令牌(user_id)


# 测试代码放 __main__ 里：只有直接运行 python auth.py 才会执行
if __name__ == "__main__":
    哈希 = 生成密码哈希("123456")
    print("哈希长这样：", 哈希[:40], "...")
    print("密码对：", 验证密码("123456", 哈希))
    print("密码错：", 验证密码("654321", 哈希))

    令牌 = 签发令牌("u001")
    print("令牌：", 令牌)
    print("验出来是：", 验证令牌(令牌))
