import asyncio
import queue
import threading

import streamlit as st
import auth
import graph

import Memory


def 流式回答(管家, q):
    """把异步大脑桥接成同步生成器——st.write_stream 只认同步的。

    思路：开一个后台线程跑 asyncio，每生成一片就塞进队列；
    主线程从队列里取，取到一片 yield 一片。队列空就阻塞等。
    """
    队列 = queue.Queue()
    结束 = object()

    def 后台跑():
        async def 收集():
            async for 片 in graph.answer_stream_async(管家, q):
                队列.put(片)

        try:
            asyncio.run(收集())
        except Exception as e:                    # 兜底：界面上要看得见
            队列.put(f"\n[出错了：{e}]")
        finally:
            队列.put(结束)

    线程 = threading.Thread(target=后台跑, daemon=True)
    线程.start()
    while True:
        片 = 队列.get()
        if 片 is 结束:
            break
        yield 片


st.title("客服小助手")

# ① 行李柜里的「用户 → 管家」通讯录（只建一次）
if "memories" not in st.session_state:
    st.session_state.memories = {}
if "user_id" not in st.session_state:
    st.session_state.user_id = None          # 没登录就是 None

# ② 没登录 → 只画登录框，画完就停（走不到下面的聊天代码）
if st.session_state.user_id is None:
    st.subheader("请先登录")
    with st.form("登录"):
        user_id = st.text_input("用户编号", value="u001")
        password = st.text_input("密码", type="password")
        提交 = st.form_submit_button("登录")
    if 提交:
        try:
            auth.登录(user_id.strip(), password)     # 密码不对会抛 登录失败
        except auth.登录失败 as e:
            st.error(str(e))
        else:
            st.session_state.user_id = user_id.strip()
            st.rerun()                              # 刷新这一页，这时候 user_id 有值了
    st.caption("演示账号：u001 / u002，密码 123456（新账号用 POST /register 注册）")
    st.stop()

user_id = st.session_state.user_id

with st.sidebar:
    st.write(f"已登录：**{user_id}**")
    if st.button("退出登录"):
        st.session_state.user_id = None
        st.session_state.memories = {}          # 顺手把管家通讯录也清空
        st.rerun()

# ③ 这个用户还没有管家？给他建一个（文件按编号分家）
if user_id not in st.session_state.memories:
    m = Memory.Memory(path=f"memory_{user_id}.json", user_id=user_id)
    m.load()                                    # 启动读盘
    st.session_state.memories[user_id] = m

# ④ 拿出这个用户的管家（多个人同时用也不会串号）
管家 = st.session_state.memories[user_id]

# ⑤ 画历史
for msg in 管家.messages:
    if msg["role"] in ("user", "assistant"):
        st.chat_message(msg["role"]).write(msg["content"])

# ⑥ 聊天：边生成边显示（流式）
q = st.chat_input("有什么可以帮您？")
if q:
    st.chat_message("user").write(q)
    with st.chat_message("assistant"):
        st.write_stream(流式回答(管家, q))
