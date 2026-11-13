"""按用户的滑动窗口限流（单进程内存版）。

原理：给每个用户记一个"最近请求时间"的队列。
每次请求先把 60 秒以前的记录扔掉，再数一数——超过上限就拒绝。
这个窗口会跟着时间往前"滑"，所以叫滑动窗口。

诚实说明它的局限（面试被问到要能答）：
1. 进程重启就清零；
2. 多进程 / 多台机器各记各的，不共享 → 生产里换成 Redis 的
   INCR + EXPIRE（计数版）或 ZSET（真正的滑动窗口），函数接口不用变；
3. 还是防不住"一个人注册很多账号轮着刷"（要防得靠按 IP / 设备指纹限流）。
"""
import time
from collections import defaultdict, deque

每分钟上限 = 10
窗口秒数 = 60

_记录 = defaultdict(deque)      # user_id → 最近 60 秒内每次请求的时间戳


def 允许(user_id):
    """这一下能不能放行？放行就顺手记一笔。"""
    现在 = time.time()
    队列 = _记录[user_id]
    while 队列 and 现在 - 队列[0] >= 窗口秒数:
        队列.popleft()
    if len(队列) >= 每分钟上限:
        return False
    队列.append(现在)
    return True


def 建议等待秒数(user_id):
    """被限流时，告诉用户大概还要等几秒。"""
    队列 = _记录.get(user_id)
    if not 队列:
        return 0
    return max(1, int(窗口秒数 - (time.time() - 队列[0])))


def 清空():
    """测试用：把所有计数清零。"""
    _记录.clear()
